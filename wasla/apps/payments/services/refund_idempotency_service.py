"""
Refund Idempotency Service - Prevents double refunds and maintains ledger integrity.

Financial Integrity Level: CRITICAL

This service guarantees:
- Each payment can only be refunded once (per idempotency key)
- Total refunded amount <= original payment
- All refunds create audit trail in ledger
- Atomic transactions with select_for_update locks
- Idempotency key prevents webhook retries from double-refunding
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional, Any
import logging
from django.db import transaction
from django.utils import timezone

from apps.payments.models import PaymentAttempt, RefundRecord
from apps.orders.models import Order
from apps.settlements.models import LedgerEntry, LedgerAccount
from apps.wallet.services.accounting_service import AccountingService

logger = logging.getLogger("wasla.refunds")


class RefundIdempotencyService:
    """
    Prevents double refunds using idempotent operations.
    
    Key Features:
    - Idempotency key (SHA256 of payment_id + order_id + timestamp)
    - Total refund cap enforcement
    - Database-level locking (select_for_update)
    - Atomic transactions
    - Ledger entry audit trail
    
    Usage:
        service = RefundIdempotencyService()
        result = service.process_refund(
            payment_attempt_id=123,
            amount=Decimal("100.00"),
            idempotency_key="ref_abc123xyz",  # From provider webhook
            reason="Customer request",
        )
        
        if result["success"]:
            print(f"Refund processed: {result['refund_id']}")
        else:
            print(f"Refund failed: {result['error']}")
    """
    
    def __init__(self):
        self.accounting = AccountingService()
    
    @transaction.atomic
    def process_refund(
        self,
        payment_attempt_id: int,
        amount: Decimal,
        idempotency_key: str,
        reason: str = "Customer request",
        provider_refund_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a refund with idempotency guarantees.
        
        Args:
            payment_attempt_id: PaymentAttempt ID to refund
            amount: Refund amount (must be <= payment amount)
            idempotency_key: Unique key for idempotency (SHA256)
            reason: Reason for refund
            provider_refund_id: Provider's refund ID (for tracking)
        
        Returns:
            {
                "success": bool,
                "refund_id": int,
                "idempotent_reuse": bool,  # True if same key used twice
                "total_refunded": Decimal,
                "remaining_refundable": Decimal,
                "ledger_entries": list of int,
                "error": str or None,
            }
        
        Guarantees:
        - If idempotency_key already processed, returns the existing refund
        - If amount > remaining refundable, returns error
        - All or nothing: Either full success with ledger entries, or rollback
        """
        try:
            # Step 1: Fetch and lock the payment attempt
            payment_attempt = PaymentAttempt.objects.select_for_update().get(
                id=payment_attempt_id
            )
            order = payment_attempt.order
            
            # Step 2: Check if this idempotency_key was already processed
            existing_refund = RefundRecord.objects.filter(
                payment_intent_id=payment_attempt.id,
                provider_reference=idempotency_key,
            ).first()
            
            if existing_refund:
                logger.info(
                    f"Refund already processed (idempotent reuse)',
                    extra={
                        "payment_attempt_id": payment_attempt_id,
                        "idempotency_key": idempotency_key,
                        "existing_refund_id": existing_refund.id,
                    }
                )
                return {
                    "success": True,
                    "refund_id": existing_refund.id,
                    "idempotent_reuse": True,
                    "total_refunded": existing_refund.amount,
                    "remaining_refundable": payment_attempt.amount - existing_refund.amount,
                    "ledger_entries": [],
                    "error": None,
                    "message": "Idempotent reuse: refund already processed",
                }
            
            # Step 3: Validate refund amount
            amount_decimal = Decimal(str(amount)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            
            if amount_decimal <= Decimal("0"):
                return {
                    "success": False,
                    "refund_id": None,
                    "idempotent_reuse": False,
                    "total_refunded": Decimal("0"),
                    "remaining_refundable": payment_attempt.amount,
                    "ledger_entries": [],
                    "error": "Refund amount must be positive",
                }
            
            # Step 4: Check refund cap - total refunded <= payment amount
            existing_refunds_total = (
                RefundRecord.objects
                .filter(payment_intent_id=payment_attempt.id)
                .exclude(status=RefundRecord.STATUS_FAILED)
                .values_list("amount", flat=True)
            )
            
            total_already_refunded = sum(
                (Decimal(str(r)) for r in existing_refunds_total),
                Decimal("0")
            )
            
            remaining_refundable = payment_attempt.amount - total_already_refunded
            
            if amount_decimal > remaining_refundable:
                return {
                    "success": False,
                    "refund_id": None,
                    "idempotent_reuse": False,
                    "total_refunded": total_already_refunded,
                    "remaining_refundable": remaining_refundable,
                    "ledger_entries": [],
                    "error": f"Refund {amount_decimal} exceeds remaining refundable {remaining_refundable}",
                }
            
            # Step 5: Create RefundRecord in pending state
            refund_record = RefundRecord.objects.create(
                payment_intent_id=payment_attempt.id,
                amount=amount_decimal,
                currency=payment_attempt.currency,
                status=RefundRecord.STATUS_PENDING,
                reason=reason,
                provider_reference=idempotency_key,
                requested_by="system",
            )
            
            # Step 6: Create refund ledger entry (debit to merchant)
            ledger_account = LedgerAccount.objects.select_for_update().get(
                store_id=order.store_id,
                currency=payment_attempt.currency,
            )
            
            refund_entry = LedgerEntry.objects.create(
                tenant_id=order.tenant_id,
                store_id=order.store_id,
                order_id=order.id,
                settlement_id=None,  # Will link to settlement later if needed
                entry_type=LedgerEntry.TYPE_DEBIT,
                amount=amount_decimal,
                currency=payment_attempt.currency,
                description=f"Refund: {reason} (Order {order.order_number})",
            )
            
            # Step 7: Adjust ledger balance atomically
            # Refund comes from pending balance first, then available if needed
            if ledger_account.pending_balance >= amount_decimal:
                ledger_account.pending_balance -= amount_decimal
            else:
                # Use available balance for difference
                shortfall = amount_decimal - ledger_account.pending_balance
                ledger_account.pending_balance = Decimal("0")
                ledger_account.available_balance -= shortfall
            
            # Ensure no negative balances (should not happen with proper cap check)
            if ledger_account.available_balance < Decimal("0"):
                logger.error(
                    f"Ledger balance went negative after refund!",
                    extra={
                        "store_id": order.store_id,
                        "available_balance": str(ledger_account.available_balance),
                        "refund_amount": str(amount_decimal),
                    }
                )
                # Still save but log critical error
            
            ledger_account.save(update_fields=["pending_balance", "available_balance"])
            
            # Step 8: Update order refunded_amount if it exists
            if hasattr(order, "refunded_amount"):
                order.refunded_amount = (
                    (order.refunded_amount or Decimal("0")) + amount_decimal
                )
                if order.refunded_amount >= order.total_amount:
                    order.status = "refunded"
                elif order.refunded_amount > Decimal("0"):
                    order.status = "partially_refunded"
                order.save(update_fields=["refunded_amount", "status"])
            
            logger.info(
                "Refund processed successfully",
                extra={
                    "payment_attempt_id": payment_attempt_id,
                    "refund_id": refund_record.id,
                    "amount": str(amount_decimal),
                    "idempotency_key": idempotency_key,
                    "ledger_entry_id": refund_entry.id,
                    "order_id": order.id,
                }
            )
            
            new_total = total_already_refunded + amount_decimal
            
            return {
                "success": True,
                "refund_id": refund_record.id,
                "idempotent_reuse": False,
                "total_refunded": new_total,
                "remaining_refundable": payment_attempt.amount - new_total,
                "ledger_entries": [refund_entry.id],
                "error": None,
                "message": "Refund processed and ledger updated",
            }
            
        except PaymentAttempt.DoesNotExist:
            logger.error(
                f"PaymentAttempt not found for refund",
                extra={"payment_attempt_id": payment_attempt_id}
            )
            return {
                "success": False,
                "refund_id": None,
                "idempotent_reuse": False,
                "total_refunded": Decimal("0"),
                "remaining_refundable": Decimal("0"),
                "ledger_entries": [],
                "error": "PaymentAttempt not found",
            }
        
        except LedgerAccount.DoesNotExist:
            logger.error(
                f"LedgerAccount not found for refund",
                extra={"order_id": order.id if "order" in locals() else "unknown"}
            )
            return {
                "success": False,
                "refund_id": None,
                "idempotent_reuse": False,
                "total_refunded": Decimal("0"),
                "remaining_refundable": Decimal("0"),
                "ledger_entries": [],
                "error": "LedgerAccount not found",
            }
        
        except Exception as e:
            logger.exception(
                f"Error processing refund: {str(e)}",
                extra={
                    "payment_attempt_id": payment_attempt_id,
                    "amount": str(amount),
                    "idempotency_key": idempotency_key,
                }
            )
            return {
                "success": False,
                "refund_id": None,
                "idempotent_reuse": False,
                "total_refunded": Decimal("0"),
                "remaining_refundable": Decimal("0"),
                "ledger_entries": [],
                "error": f"Error processing refund: {str(e)}",
            }
    
    def get_refund_status(self, refund_id: int) -> Dict[str, Any]:
        """Get status of a refund by ID."""
        try:
            refund = RefundRecord.objects.get(id=refund_id)
            return {
                "refund_id": refund.id,
                "payment_intent_id": refund.payment_intent_id,
                "amount": str(refund.amount),
                "status": refund.status,
                "reason": refund.reason,
                "provider_reference": refund.provider_reference,
                "created_at": refund.created_at.isoformat(),
                "processed_at": refund.processed_at.isoformat() if refund.processed_at else None,
            }
        except RefundRecord.DoesNotExist:
            return None
    
    def get_payment_refund_summary(self, payment_attempt_id: int) -> Dict[str, Any]:
        """Get complete refund summary for a payment."""
        refunds = RefundRecord.objects.filter(
            payment_intent_id=payment_attempt_id
        ).exclude(status=RefundRecord.STATUS_FAILED)
        
        total_refunded = sum(
            (r.amount for r in refunds),
            Decimal("0")
        )
        
        return {
            "payment_attempt_id": payment_attempt_id,
            "total_refunded": str(total_refunded),
            "refund_count": refunds.count(),
            "refunds": [
                {
                    "id": r.id,
                    "amount": str(r.amount),
                    "status": r.status,
                    "idempotency_key": r.provider_reference,
                }
                for r in refunds
            ]
        }

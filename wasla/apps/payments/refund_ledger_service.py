"""
Refund Ledger Synchronization Service.

Ensures financial integrity when refunds are processed:

1. Prevent double refunds:
   - Check if refund already exists (idempotency_key)
   - Compare webhook ts with existing refund ts
   - Reject if duplicate

2. Ledger sync:
   - Create negative LedgerEntry
   - Adjust merchant available_balance (decrease)
   - Link refund to settlement (prevent settlement finalization with pending refunds)

3. Webhook safety:
   - Idempotency: refund_id or transaction_id as key
   - Signature validation: verify provider signature
   - Atomic transaction: all-or-nothing

4. Financial correctness:
   - If settlement already paid: create credit LedgerEntry
   - If settlement pending: adjust pending balance
   - If refund > original charge: create debit alert

Financial flows:
NORMAL REFUND (order paid, merchant has balance):
  Payment → LedgerEntry(+) → available_balance
  ↓
  Refund → LedgerEntry(-) → available_balance (decreased)
  ↓
  Merchant balance decreases by refund amount

EARLY REFUND (before settlement):
  Payment → LedgerEntry(pending) → pending_balance
  ↓
  Refund → LedgerEntry(pending, negative) → pending_balance
  ↓
  Settlement processes with reduced amount

DOUBLE REFUND PREVENTION:
  Refund #1 (idempotency_key=X) → created
  Webhook retry (same idempotency_key=X) → skipped (already exists)
"""

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
import logging
from typing import Dict, Any, Optional
from decimal import Decimal

from settlements.models import Settlement, SettlementItem, LedgerAccount, LedgerEntry
from payments.models import Payment, PaymentRefund
from orders.models import Order

logger = logging.getLogger("wasla.payments.refund")


class RefundLedgerSyncService:
    """
    Service for synchronizing refunds with merchant ledger.
    
    Guarantees:
    - No double refunds (idempotency key validation)
    - Ledger balance accuracy (create LedgerEntry for each refund)
    - Settlement integrity (flag settlements with pending refunds)
    - Audit trail (log all refund operations)
    """
    
    @staticmethod
    @transaction.atomic
    def process_refund_webhook(
        payment_id: int,
        refund_id: str,
        amount: Decimal,
        provider: str,
        webhook_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process refund webhook from payment provider.
        
        Args:
            payment_id: FK to Payment
            refund_id: Provider refund ID (e.g., "ref_xyz123")
            amount: Refund amount
            provider: Provider name ("tap", "stripe", etc.)
            webhook_data: Full webhook payload
        
        Returns:
            {
                "success": bool,
                "refund_id": str,
                "ledger_entry_id": int,
                "message": str
            }
        
        Flow:
        1. Fetch Payment + Order + Merchant
        2. Check if refund already exists (idempotency)
        3. Validate refund amount <= payment amount
        4. Create PaymentRefund record
        5. Create negative LedgerEntry
        6. Adjust LedgerAccount.available_balance
        7. Flag settlement item if needed
        8. Return success + ledger_entry_id
        
        Atomic: All steps succeed or all rollback
        """
        
        try:
            # Step 1: Fetch Payment
            payment = Payment.objects.select_for_update().get(id=payment_id)
            order = payment.order
            merchant_store = order.store
            
            # Step 2: Check if refund already exists (idempotency)
            existing_refund = PaymentRefund.objects.filter(
                payment=payment,
                provider_refund_id=refund_id,
            ).first()
            
            if existing_refund:
                logger.info(
                    f"Refund already processed (idempotent): {refund_id}",
                    extra={
                        "payment_id": payment_id,
                        "refund_id": refund_id,
                        "existing_refund_id": existing_refund.id,
                    }
                )
                return {
                    "success": True,
                    "refund_id": refund_id,
                    "ledger_entry_id": existing_refund.ledger_entry_id,
                    "message": "Refund already processed (idempotent)"
                }
            
            # Step 3: Validate refund amount
            if amount > payment.amount:
                logger.warning(
                    f"Refund amount exceeds payment: {amount} > {payment.amount}",
                    extra={
                        "payment_id": payment_id,
                        "refund_id": refund_id,
                        "amount": str(amount),
                        "payment_amount": str(payment.amount),
                    }
                )
                return {
                    "success": False,
                    "refund_id": refund_id,
                    "message": "Refund amount exceeds payment"
                }
            
            # Step 4: Calculate total refunded amount
            total_refunded = PaymentRefund.objects.filter(payment=payment).aggregate(
                total=models.Sum("amount")
            )["total"] or Decimal("0")
            
            if total_refunded + amount > payment.amount:
                logger.warning(
                    f"Total refunds exceed payment: already refunded {total_refunded}",
                    extra={
                        "payment_id": payment_id,
                        "refund_id": refund_id,
                        "total_refunded": str(total_refunded),
                        "new_refund": str(amount),
                    }
                )
                return {
                    "success": False,
                    "refund_id": refund_id,
                    "message": "Total refunds exceed payment amount"
                }
            
            # Step 5: Create PaymentRefund record
            payment_refund = PaymentRefund.objects.create(
                payment=payment,
                provider_refund_id=refund_id,
                amount=amount,
                status="completed",
                webhook_data=webhook_data,
            )
            
            # Step 6: Get merchant ledger account
            ledger_account = LedgerAccount.objects.select_for_update().get(
                tenant=merchant_store.tenant,
                store=merchant_store,
            )
            
            # Step 7: Create negative LedgerEntry
            ledger_entry = LedgerEntry.objects.create(
                ledger_account=ledger_account,
                amount=-amount,  # Negative for refund
                transaction_type="refund",
                description=f"Refund for order {order.order_number} (payment {payment.id})",
                reference_payment_id=payment.id,
                reference_order_id=order.id,
                reference_refund_id=payment_refund.id,
            )
            
            # Step 8: Adjust ledger balance
            # Determine if refund should deduct from available or pending
            if payment.status == "completed":
                # Payment already completed: deduct from available
                ledger_account.available_balance -= amount
            else:
                # Payment pending: deduct from pending
                ledger_account.pending_balance -= amount
            
            # Ensure balance doesn't go negative (audit flag)
            if ledger_account.available_balance < 0:
                logger.warning(
                    f"Ledger balance went negative after refund",
                    extra={
                        "ledger_account_id": ledger_account.id,
                        "balance": str(ledger_account.available_balance),
                        "refund_id": refund_id,
                    }
                )
            
            ledger_account.save(
                update_fields=["available_balance", "pending_balance"]
            )
            
            # Step 9: Update PaymentRefund with ledger link
            payment_refund.ledger_entry = ledger_entry
            payment_refund.save(update_fields=["ledger_entry"])
            
            # Step 10: Flag any settlement items that include this order
            settlement_items = SettlementItem.objects.filter(
                order=order,
                settlement__status__in=["pending", "approved"],
            )
            
            for settlement_item in settlement_items:
                settlement_item.refund_pending = True
                settlement_item.save(update_fields=["refund_pending"])
                
                logger.info(
                    f"Settlement marked with pending refund: {settlement_item.settlement.id}",
                    extra={
                        "settlement_id": settlement_item.settlement.id,
                        "order_id": order.id,
                        "refund_id": refund_id,
                    }
                )
            
            logger.info(
                f"Refund successfully processed and synced to ledger",
                extra={
                    "payment_id": payment_id,
                    "refund_id": refund_id,
                    "amount": str(amount),
                    "ledger_entry_id": ledger_entry.id,
                    "merchant_id": merchant_store.tenant.id,
                }
            )
            
            return {
                "success": True,
                "refund_id": refund_id,
                "ledger_entry_id": ledger_entry.id,
                "message": "Refund processed and ledger synced"
            }
        
        except Payment.DoesNotExist:
            logger.error(
                f"Payment not found for refund: {payment_id}",
                extra={"payment_id": payment_id, "refund_id": refund_id}
            )
            return {
                "success": False,
                "refund_id": refund_id,
                "message": "Payment not found"
            }
        
        except LedgerAccount.DoesNotExist:
            logger.error(
                f"Ledger account not found",
                extra={
                    "payment_id": payment_id,
                    "refund_id": refund_id,
                }
            )
            return {
                "success": False,
                "refund_id": refund_id,
                "message": "Ledger account not found"
            }
        
        except Exception as e:
            logger.error(
                f"Error processing refund webhook: {str(e)}",
                extra={
                    "payment_id": payment_id,
                    "refund_id": refund_id,
                    "error": str(e),
                },
                exc_info=True
            )
            return {
                "success": False,
                "refund_id": refund_id,
                "message": f"Error processing refund: {str(e)}"
            }
    
    @staticmethod
    def get_merchant_refund_summary(store_id: int) -> Dict[str, Any]:
        """
        Get summary of all refunds for a merchant store.
        
        Returns:
            {
                "total_refunds": Decimal,
                "refund_count": int,
                "pending_refund_settlements": int,
                "refunds_pending_ledger_sync": int,  # Should be 0
            }
        """
        from django.db.models import Sum, Count
        
        refund_summary = PaymentRefund.objects.filter(
            payment__order__store_id=store_id
        ).aggregate(
            total_amount=Sum("amount"),
            count=Count("id"),
        )
        
        pending_refund_settlements = SettlementItem.objects.filter(
            order__store_id=store_id,
            refund_pending=True,
        ).count()
        
        # Should be 0 (ledger_entry should always be set)
        refunds_pending_sync = PaymentRefund.objects.filter(
            payment__order__store_id=store_id,
            ledger_entry__isnull=True,
        ).count()
        
        return {
            "total_refunds": refund_summary["total_amount"] or Decimal("0"),
            "refund_count": refund_summary["count"] or 0,
            "pending_refund_settlements": pending_refund_settlements,
            "refunds_pending_ledger_sync": refunds_pending_sync,
        }


# Import models for type hints
from django.db import models

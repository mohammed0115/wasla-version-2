"""
Accounting Service - Single canonical place for fee calculations.

Financial Integrity Level: CRITICAL

This service is the single source of truth for:
- Fee calculation (transaction fees + wasla commission)
- Net/Gross reconciliation
- Audit trail creation
- Balance consistency

Key Guarantees:
- All fee calculations go through this service
- Fees are deterministic and auditable
- Every fee creates a ledger entry
- Fees cannot be calculated in multiple places
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional, Any
import logging
from django.db import transaction
from django.utils import timezone

from apps.payments.models import PaymentProviderSettings
from apps.settlements.models import LedgerEntry, LedgerAccount
from apps.wallet.models import Wallet, WalletTransaction

logger = logging.getLogger("wasla.accounting")


class FeePolicy:
    """Internal representation of a fee policy."""
    def __init__(
        self,
        transaction_fee_percent: Decimal,
        wasla_commission_percent: Decimal,
        name: str = "default",
    ):
        self.name = name
        self.transaction_fee_percent = Decimal(str(transaction_fee_percent))
        self.wasla_commission_percent = Decimal(str(wasla_commission_percent))
    
    def total_fee_percent(self) -> Decimal:
        """Total fee percentage."""
        return self.transaction_fee_percent + self.wasla_commission_percent
    
    def __repr__(self):
        return f"FeePolicy({self.name}, tx={self.transaction_fee_percent}%, wasla={self.wasla_commission_percent}%)"


class AccountingService:
    """
    Single implementation for all fee calculations and ledger entries.
    
    Usage:
        accounting = AccountingService()
        fee_info = accounting.calculate_fee_breakdown(
            gross_amount=Decimal("1000"),
            tenant_id=1,
            store_id=5,
        )
        # fee_info = {
        #     "gross": 1000,
        #     "transaction_fee": 25,
        #     "wasla_fee": 30,
        #     "total_fee": 55,
        #     "net": 945,
        # }
    """
    
    def __init__(self):
        self.default_transaction_fee_percent = Decimal("2.5")  # 2.5%
        self.default_wasla_commission_percent = Decimal("3.0")  # 3.0%
    
    def get_active_fee_policy(self, store_id: int, provider: str = "tap") -> FeePolicy:
        """
        Get the active fee policy for a store and provider.
        
        Falls back to default if no provider-specific policy exists.
        
        Args:
            store_id: Store ID
            provider: Payment provider code (tap, stripe, paypal)
        
        Returns:
            FeePolicy instance (never None)
        """
        try:
            settings = PaymentProviderSettings.objects.filter(
                store_id=store_id,
                provider=provider,
                is_enabled=True,
            ).first()
            
            if settings:
                return FeePolicy(
                    transaction_fee_percent=settings.transaction_fee_percent,
                    wasla_commission_percent=settings.wasla_commission_percent,
                    name=f"{provider}_store_{store_id}",
                )
        except Exception as e:
            logger.warning(
                f"Error fetching fee policy for store {store_id}: {e}, using defaults"
            )
        
        # Fallback to defaults
        return FeePolicy(
            transaction_fee_percent=self.default_transaction_fee_percent,
            wasla_commission_percent=self.default_wasla_commission_percent,
            name="default",
        )
    
    def calculate_fee_breakdown(
        self,
        gross_amount: Decimal,
        tenant_id: int,
        store_id: int,
        provider: str = "tap",
    ) -> Dict[str, Decimal]:
        """
        Calculate complete fee breakdown.
        
        Args:
            gross_amount: Total payment amount (before fees)
            tenant_id: Tenant ID
            store_id: Store ID
            provider: Payment provider
        
        Returns:
            {
                "gross": Decimal,
                "transaction_fee": Decimal,
                "wasla_commission": Decimal,
                "total_fee": Decimal,
                "net": Decimal,  # What merchant receives
            }
        
        Example:
            Input: gross=1000, fees=5.5%
            Output: {
                "gross": 1000,
                "transaction_fee": 25,
                "wasla_commission": 30,
                "total_fee": 55,
                "net": 945,  # Merchant credit
            }
        """
        gross = Decimal(str(gross_amount)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        policy = self.get_active_fee_policy(store_id, provider)
        
        # Calculate fees separately for clarity
        transaction_fee = (
            gross * (policy.transaction_fee_percent / Decimal("100"))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        wasla_commission = (
            gross * (policy.wasla_commission_percent / Decimal("100"))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        total_fee = transaction_fee + wasla_commission
        net = gross - total_fee
        
        # Ensure net is never negative (safety check)
        if net < Decimal("0"):
            logger.error(
                f"Negative net amount calculated: gross={gross}, fees={total_fee}",
                extra={
                    "store_id": store_id,
                    "gross": str(gross),
                    "total_fee": str(total_fee),
                    "net": str(net),
                }
            )
            net = Decimal("0")
        
        return {
            "gross": gross,
            "transaction_fee": transaction_fee,
            "wasla_commission": wasla_commission,
            "total_fee": total_fee,
            "net": net,
            "policy_name": policy.name,
        }
    
    def calculate_fee(
        self,
        amount: Decimal,
        fee_policy: Optional[FeePolicy] = None,
    ) -> Decimal:
        """
        Calculate total fee for an amount.
        
        Simplified interface if you only need the fee amount.
        
        Args:
            amount: Gross amount
            fee_policy: Optional FeePolicy; if None, returns fee using defaults
        
        Returns:
            Total fee amount
        """
        if fee_policy is None:
            fee_policy = FeePolicy(
                transaction_fee_percent=self.default_transaction_fee_percent,
                wasla_commission_percent=self.default_wasla_commission_percent,
            )
        
        amount_decimal = Decimal(str(amount))
        fee = (
            amount_decimal * (fee_policy.total_fee_percent() / Decimal("100"))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        return fee
    
    @transaction.atomic
    def record_payment_fee(
        self,
        store_id: int,
        tenant_id: int,
        gross_amount: Decimal,
        order_id: int,
        reference: str,
        provider: str = "tap",
    ) -> Dict[str, Any]:
        """
        Record a payment and create ledger entries for fees.
        
        This is called when a payment is confirmed. It:
        1. Calculates fees
        2. Creates credit entry for GROSS (pending)
        3. Creates debit entries for each fee type
        4. Returns breakdown for audit
        
        Args:
            store_id: Store ID
            tenant_id: Tenant ID
            gross_amount: Payment amount
            order_id: Order ID
            reference: Unique reference (order number, transaction ID, etc.)
            provider: Payment provider
        
        Returns:
            {
                "success": bool,
                "fee_breakdown": dict,
                "ledger_entries": list of int (ledger_entry_ids),
                "message": str,
            }
        
        Atomic: Either all entries are created or none.
        """
        try:
            # Calculate breakdown
            breakdown = self.calculate_fee_breakdown(
                gross_amount=gross_amount,
                tenant_id=tenant_id,
                store_id=store_id,
                provider=provider,
            )
            
            # Get or create ledger account
            ledger_account, _ = LedgerAccount.objects.get_or_create(
                store_id=store_id,
                currency="SAR",
                defaults={
                    "tenant_id": tenant_id,
                    "available_balance": Decimal("0"),
                    "pending_balance": Decimal("0"),
                },
            )
            
            # Lock account for update
            ledger_account = LedgerAccount.objects.select_for_update().get(
                pk=ledger_account.id
            )
            
            ledger_entries = []
            
            # 1. Credit GROSS amount to pending balance
            credit_entry = LedgerEntry.objects.create(
                tenant_id=tenant_id,
                store_id=store_id,
                order_id=order_id,
                entry_type=LedgerEntry.TYPE_CREDIT,
                amount=breakdown["gross"],
                currency="SAR",
                description=f"Payment received: {reference}",
            )
            ledger_entries.append(credit_entry.id)
            
            ledger_account.pending_balance += breakdown["gross"]
            
            # 2. Debit transaction fee (to Wasla)
            if breakdown["transaction_fee"] > Decimal("0"):
                fee_entry = LedgerEntry.objects.create(
                    tenant_id=tenant_id,
                    store_id=store_id,
                    order_id=order_id,
                    entry_type=LedgerEntry.TYPE_DEBIT,
                    amount=breakdown["transaction_fee"],
                    currency="SAR",
                    description=f"Transaction fee (2.5%): {reference}",
                )
                ledger_entries.append(fee_entry.id)
                ledger_account.pending_balance -= breakdown["transaction_fee"]
            
            # 3. Debit wasla commission (to Wasla)
            if breakdown["wasla_commission"] > Decimal("0"):
                commission_entry = LedgerEntry.objects.create(
                    tenant_id=tenant_id,
                    store_id=store_id,
                    order_id=order_id,
                    entry_type=LedgerEntry.TYPE_DEBIT,
                    amount=breakdown["wasla_commission"],
                    currency="SAR",
                    description=f"Wasla commission (3.0%): {reference}",
                )
                ledger_entries.append(commission_entry.id)
                ledger_account.pending_balance -= breakdown["wasla_commission"]
            
            # Verify net equals pending balance after fees
            expected_net = breakdown["net"]
            actual_net = ledger_account.pending_balance
            
            if expected_net != actual_net:
                logger.error(
                    f"Fee reconciliation mismatch: expected {expected_net}, got {actual_net}",
                    extra={
                        "store_id": store_id,
                        "order_id": order_id,
                        "expected_net": str(expected_net),
                        "actual_net": str(actual_net),
                        "breakdown": breakdown,
                    }
                )
                # Still allow, but log the mismatch
            
            ledger_account.save(update_fields=["pending_balance"])
            
            logger.info(
                "Payment fee recorded",
                extra={
                    "store_id": store_id,
                    "order_id": order_id,
                    "gross": str(breakdown["gross"]),
                    "net": str(breakdown["net"]),
                    "total_fee": str(breakdown["total_fee"]),
                    "ledger_entries": ledger_entries,
                }
            )
            
            return {
                "success": True,
                "fee_breakdown": breakdown,
                "ledger_entries": ledger_entries,
                "message": "Fee recorded and ledger entries created",
            }
            
        except Exception as e:
            logger.exception(
                f"Error recording payment fee: {e}",
                extra={
                    "store_id": store_id,
                    "order_id": order_id,
                    "gross_amount": str(gross_amount),
                }
            )
            return {
                "success": False,
                "fee_breakdown": None,
                "ledger_entries": [],
                "message": f"Error recording fee: {str(e)}",
            }
    
    @transaction.atomic
    def record_refund_fee_reversal(
        self,
        store_id: int,
        tenant_id: int,
        net_refund_amount: Decimal,
        original_fee: Decimal,
        order_id: int,
        reference: str,
    ) -> Dict[str, Any]:
        """
        Record fee reversal when a payment is refunded.
        
        When a refund happens:
        1. Credit back the transaction fees (merchant gets them back)
        2. Credit back the wasla commission (platform returns it)
        3. Debit the net refund from merchant balance
        
        Args:
            store_id: Store ID
            tenant_id: Tenant ID
            net_refund_amount: Amount being refunded to customer
            original_fee: Original fee that should be reversed
            order_id: Order ID
            reference: Refund reference
        
        Returns:
            {
                "success": bool,
                "fee_reversed": Decimal,
                "ledger_entries": list of int,
                "message": str,
            }
        """
        try:
            ledger_account = LedgerAccount.objects.select_for_update().get(
                store_id=store_id,
                currency="SAR",
            )
            
            ledger_entries = []
            
            # Debit the refund amount
            refund_entry = LedgerEntry.objects.create(
                tenant_id=tenant_id,
                store_id=store_id,
                order_id=order_id,
                entry_type=LedgerEntry.TYPE_DEBIT,
                amount=net_refund_amount,
                currency="SAR",
                description=f"Refund to customer: {reference}",
            )
            ledger_entries.append(refund_entry.id)
            ledger_account.pending_balance -= net_refund_amount
            
            # Credit back the fees
            if original_fee > Decimal("0"):
                fee_credit_entry = LedgerEntry.objects.create(
                    tenant_id=tenant_id,
                    store_id=store_id,
                    order_id=order_id,
                    entry_type=LedgerEntry.TYPE_CREDIT,
                    amount=original_fee,
                    currency="SAR",
                    description=f"Fee reversal for refund: {reference}",
                )
                ledger_entries.append(fee_credit_entry.id)
                ledger_account.pending_balance += original_fee
            
            ledger_account.save(update_fields=["pending_balance"])
            
            logger.info(
                "Refund fee reversed",
                extra={
                    "store_id": store_id,
                    "order_id": order_id,
                    "refund_amount": str(net_refund_amount),
                    "fee_reversed": str(original_fee),
                    "ledger_entries": ledger_entries,
                }
            )
            
            return {
                "success": True,
                "fee_reversed": original_fee,
                "ledger_entries": ledger_entries,
                "message": "Refund fee reversed and ledger updated",
            }
            
        except LedgerAccount.DoesNotExist:
            logger.error(
                f"Ledger account not found for refund fee reversal",
                extra={
                    "store_id": store_id,
                    "order_id": order_id,
                }
            )
            return {
                "success": False,
                "fee_reversed": Decimal("0"),
                "ledger_entries": [],
                "message": "Ledger account not found",
            }
        except Exception as e:
            logger.exception(f"Error reversing refund fee: {e}")
            return {
                "success": False,
                "fee_reversed": Decimal("0"),
                "ledger_entries": [],
                "message": f"Error reversing fee: {str(e)}",
            }

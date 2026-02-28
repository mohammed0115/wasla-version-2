"""
Platform Fee Automation Service.

Implements automatic fee calculation and deduction during settlement creation.

Features:
1. Per-store platform fee percentage (configurable)
2. Auto-deduction during settlement creation
3. Fee ledger entries (audit trail)
4. Fee adjustment (admin override)
5. Tiered fee schedules (future)

Formula:
net_amount = gross_amount - (gross_amount * platform_fee_percentage)

Example:
Order: 100 SAR
Platform fee: 5% (0.05)
Fee amount: 100 * 0.05 = 5 SAR
Net to merchant: 100 - 5 = 95 SAR

Financial flows:
Order created $100 → Payment.amount = 100
Settlement period:
  - Gross (orders sum): 100
  - Platform fee (5%): 5
  - Net (sent to merchant): 95
  - Platform revenue: 5 (goes to platform)

Ledger entries:
1. Gross amount → Merchant available_balance (+100)
2. Fee amount → Platform revenue account (+5)
3. Net amount → actually paid to merchant (95)
"""

from django.db import transaction
from django.utils import timezone
from typing import Dict, Any, Optional
from decimal import Decimal
import logging

from settlements.models import Settlement, SettlementItem, LedgerEntry, LedgerAccount
from stores.models import Store

logger = logging.getLogger("wasla.settlements")


class StoreFeeConfig(models.Model):
    """
    Store-specific fee configuration.
    
    Fields:
    - store: FK to Store
    - platform_fee_percentage: Fee % (e.g., 5 = 5%)
    - effective_from: When this fee schedule starts
    - active: Whether config is active
    """
    
    store = models.OneToOneField(
        Store,
        on_delete=models.CASCADE,
        related_name="fee_config"
    )
    
    # Fee as percentage (5 = 5%, 2.5 = 2.5%)
    platform_fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("5.0"),
        help_text="Platform fee as percentage (e.g., 5 = 5%)"
    )
    
    effective_from = models.DateField(
        default=timezone.now,
        help_text="When this fee schedule becomes active"
    )
    
    active = models.BooleanField(
        default=True,
        help_text="Whether this config is active"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "settlements_store_fee_config"
    
    def __str__(self):
        return f"Fee config for {self.store.name}: {self.platform_fee_percentage}%"


class PlatformFeeService:
    """Service for calculating and applying platform fees."""
    
    @staticmethod
    def get_store_fee_percentage(store: Store) -> Decimal:
        """
        Get platform fee % for store.
        
        Returns:
            Decimal fee percentage (e.g., Decimal("5") for 5%)
        
        Falls back to default 5% if no config exists.
        """
        try:
            fee_config = store.fee_config
            if fee_config.active:
                return fee_config.platform_fee_percentage
        except StoreFeeConfig.DoesNotExist:
            pass
        
        # Default: 5%
        return Decimal("5.0")
    
    @staticmethod
    def calculate_fee(gross_amount: Decimal, fee_percentage: Decimal) -> Decimal:
        """
        Calculate fee amount.
        
        Args:
            gross_amount: Total order amount
            fee_percentage: Fee as percentage (e.g., 5 = 5%)
        
        Returns:
            Fee amount (rounded to 2 decimals)
        
        Example:
            gross=100, fee=5%
            → fee = 100 * (5/100) = 5
        """
        fee = gross_amount * (fee_percentage / Decimal("100"))
        return fee.quantize(Decimal("0.01"))
    
    @staticmethod
    def calculate_net(gross_amount: Decimal, fee_percentage: Decimal) -> Decimal:
        """
        Calculate net amount (after fee).
        
        Args:
            gross_amount: Total order amount
            fee_percentage: Fee as percentage
        
        Returns:
            Net amount for merchant
        
        Example:
            gross=100, fee=5%
            → net = 100 - (100 * 0.05) = 95
        """
        fee = PlatformFeeService.calculate_fee(gross_amount, fee_percentage)
        return gross_amount - fee
    
    @staticmethod
    @transaction.atomic
    def create_settlement_with_fees(
        store: Store,
        period_start: timezone.datetime,
        period_end: timezone.datetime,
        settlement_items: list,
    ) -> Dict[str, Any]:
        """
        Create settlement with automatic fee calculation and deduction.
        
        Args:
            store: Store instance
            period_start: Settlement period start
            period_end: Settlement period end
            settlement_items: List of SettlementItem already created
        
        Returns:
            {
                "settlement_id": int,
                "gross_amount": Decimal,
                "platform_fee": Decimal,
                "net_amount": Decimal,
            }
        
        Flow:
        1. Get all orders in period
        2. Calculate gross amount
        3. Get store fee %
        4. Calculate fee amount
        5. Calculate net amount
        6. Create Settlement record
        7. Create fee LedgerEntry to platform account
        8. Create merchant credit LedgerEntry (gross)
        9. Create fee deduction LedgerEntry (negative)
        10. Update merchant available_balance (only net)
        
        Atomic: All succeed or all rollback
        """
        from django.db.models import Sum
        from settlements.models import Settlement
        
        try:
            # Step 1: Calculate gross amount
            gross_amount = SettlementItem.objects.filter(
                settlement__isnull=True,
                order__store=store,
                order__created_at__gte=period_start,
                order__created_at__lt=period_end,
            ).aggregate(
                total=Sum("order__payment__amount")
            )["total"] or Decimal("0")
            
            # Step 2: Get fee percentage
            fee_percentage = PlatformFeeService.get_store_fee_percentage(store)
            
            # Step 3: Calculate fee amount
            fee_amount = PlatformFeeService.calculate_fee(gross_amount, fee_percentage)
            
            # Step 4: Calculate net amount
            net_amount = PlatformFeeService.calculate_net(gross_amount, fee_percentage)
            
            # Step 5: Create Settlement
            settlement = Settlement.objects.create(
                tenant=store.tenant,
                store=store,
                period_start=period_start,
                period_end=period_end,
                gross_amount=gross_amount,
                fees_amount=fee_amount,
                net_amount=net_amount,
                status="created",
            )
            
            # Step 6: Get merchant ledger account
            merchant_ledger = LedgerAccount.objects.select_for_update().get(
                tenant=store.tenant,
                store=store,
            )
            
            # Step 7: Create fee LedgerEntry
            # Fee goes to platform revenue account
            fee_ledger_entry = LedgerEntry.objects.create(
                ledger_account=merchant_ledger,
                amount=-fee_amount,  # Negative: deduction from merchant
                transaction_type="platform_fee",
                description=f"Platform fee ({fee_percentage}%) for settlement {settlement.id}",
                reference_settlement_id=settlement.id,
            )
            
            # Step 8: Create gross amount entry
            gross_ledger_entry = LedgerEntry.objects.create(
                ledger_account=merchant_ledger,
                amount=net_amount,  # Only net is added to merchant balance
                transaction_type="settlement",
                description=f"Settlement {settlement.id} (after fees)",
                reference_settlement_id=settlement.id,
            )
            
            # Step 9: Update merchant balance
            # Only net amount goes to merchant (gross - fee)
            merchant_ledger.available_balance += net_amount
            merchant_ledger.save(update_fields=["available_balance"])
            
            logger.info(
                f"Settlement created with fees",
                extra={
                    "settlement_id": settlement.id,
                    "store_id": store.id,
                    "gross_amount": str(gross_amount),
                    "platform_fee": str(fee_amount),
                    "fee_percentage": str(fee_percentage),
                    "net_amount": str(net_amount),
                }
            )
            
            return {
                "settlement_id": settlement.id,
                "gross_amount": gross_amount,
                "platform_fee": fee_amount,
                "fee_percentage": fee_percentage,
                "net_amount": net_amount,
            }
        
        except Exception as e:
            logger.error(
                f"Error creating settlement with fees: {str(e)}",
                extra={
                    "store_id": store.id,
                    "error": str(e),
                },
                exc_info=True
            )
            raise
    
    @staticmethod
    def adjust_fee(settlement: Settlement, new_fee_amount: Decimal) -> bool:
        """
        Adjust platform fee for settlement (admin override).
        
        Args:
            settlement: Settlement instance
            new_fee_amount: New fee amount
        
        Returns:
            True if adjusted, False if cannot adjust (settlement already paid)
        
        Scenarios:
        1. Settlement pending → adjust fee + recalculate net ✓
        2. Settlement paid → create credit/debit LedgerEntry (don't modify settlement)
        
        When fee is adjusted:
        - Update settlement.fees_amount
        - Recalculate settlement.net_amount
        - Create adjustment LedgerEntry
        - Update merchant balance by difference
        """
        
        if settlement.status == "paid":
            # Cannot modify paid settlement
            logger.warning(
                f"Cannot adjust fee for paid settlement: {settlement.id}",
                extra={"settlement_id": settlement.id}
            )
            return False
        
        try:
            old_fee = settlement.fees_amount
            fee_difference = new_fee_amount - old_fee
            
            # Recalculate net
            settlement.fees_amount = new_fee_amount
            settlement.net_amount = settlement.gross_amount - new_fee_amount
            settlement.save(update_fields=["fees_amount", "net_amount"])
            
            # Create adjustment LedgerEntry
            merchant_ledger = LedgerAccount.objects.get(
                tenant=settlement.tenant,
                store=settlement.store,
            )
            
            LedgerEntry.objects.create(
                ledger_account=merchant_ledger,
                amount=fee_difference,  # Positive if fee decreased, negative if increased
                transaction_type="fee_adjustment",
                description=f"Fee adjustment for settlement {settlement.id}: {old_fee} → {new_fee_amount}",
                reference_settlement_id=settlement.id,
            )
            
            # Update merchant balance
            merchant_ledger.available_balance += fee_difference
            merchant_ledger.save(update_fields=["available_balance"])
            
            logger.info(
                f"Settlement fee adjusted",
                extra={
                    "settlement_id": settlement.id,
                    "old_fee": str(old_fee),
                    "new_fee": str(new_fee_amount),
                    "difference": str(fee_difference),
                }
            )
            
            return True
        
        except Exception as e:
            logger.error(
                f"Error adjusting settlement fee: {str(e)}",
                extra={"settlement_id": settlement.id},
                exc_info=True
            )
            return False


from django.db import models

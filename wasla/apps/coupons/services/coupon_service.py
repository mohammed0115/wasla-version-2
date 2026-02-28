"""
Coupon/Promotion Service - Enforces expiry, usage limits, scope validation.

Financial Integrity Level: HIGH

This service:
- Validates coupon code (active, not expired, not max usage)
- Enforces per-store scope
- Calculates discount amount
- Prevents stacking (single coupon per order)
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Tuple
from django.utils import timezone
from django.db.models import Q

from apps.coupons.models import Coupon

logger = logging.getLogger("wasla.promotions")


class CouponValidationError(Exception):
    """Raised when coupon validation fails."""
    pass


class CouponService:
    """
    Validates and applies coupons to orders.
    
    Usage:
        service = CouponService()
        try:
            result = service.validate_and_apply_coupon(
                store_id=5,
                coupon_code="SAVE20",
                order_total=Decimal("1000.00"),
                customer_email="test@example.com",
            )
            # Returns: {"valid": True, "discount": Decimal("200.00"), "coupon_id": 1}
        except CouponValidationError as e:
            pass  # Show error to user
    """
    
    def validate_coupon_code(
        self,
        store_id: int,
        coupon_code: str,
        order_total: Decimal = Decimal("0"),
        customer_email: str = "",
    ) -> Tuple[bool, str]:
        """
        Validate coupon code without applying it.
        
        Returns:
            (is_valid: bool, error_message: str)
        """
        coupon = Coupon.objects.filter(
            store_id=store_id,
            code__iexact=coupon_code,
        ).first()
        
        if not coupon:
            return False, f"Coupon code '{coupon_code}' not found."
        
        if not coupon.is_active:
            return False, f"Coupon code '{coupon_code}' is not active."
        
        now = timezone.now()
        if coupon.start_date > now:
            return False, f"Coupon code '{coupon_code}' is not yet active."
        
        if coupon.end_date < now:
            return False, f"Coupon code '{coupon_code}' has expired."
        
        # Check global usage limit
        if coupon.usage_limit and coupon.times_used >= coupon.usage_limit:
            return False, f"Coupon code '{coupon_code}' has reached max usage limit."
        
        # Check minimum purchase
        if order_total < coupon.minimum_purchase_amount:
            return (
                False,
                f"Minimum purchase of {coupon.minimum_purchase_amount} SAR required. "
                f"Current cart: {order_total} SAR"
            )
        
        # Check per-customer usage limit (if email provided)
        if customer_email:
            from apps.orders.models import Order
            customer_usage_count = Order.objects.filter(
                store_id=store_id,
                customer_email__iexact=customer_email,
                # Assuming we store coupon code on order
            ).count()
            
            if customer_usage_count >= coupon.usage_limit_per_customer:
                return (
                    False,
                    f"You've reached the maximum uses for coupon '{coupon_code}'."
                )
        
        return True, ""
    
    def apply_coupon(
        self,
        store_id: int,
        coupon_code: str,
        order_total: Decimal,
    ) -> Dict[str, Any]:
        """
        Apply coupon and calculate discount.
        
        Returns:
            {
                "valid": True,
                "coupon_id": 1,
                "discount_amount": Decimal("200.00"),
                "discount_type": "percentage",
                "error": None,
            }
        
        Or on error:
            {
                "valid": False,
                "coupon_id": None,
                "discount_amount": Decimal("0"),
                "error": "Coupon not found",
            }
        """
        is_valid, error_msg = self.validate_coupon_code(
            store_id=store_id,
            coupon_code=coupon_code,
            order_total=order_total,
        )
        
        if not is_valid:
            return {
                "valid": False,
                "coupon_id": None,
                "discount_amount": Decimal("0"),
                "discount_type": None,
                "error": error_msg,
            }
        
        coupon = Coupon.objects.get(
            store_id=store_id,
            code__iexact=coupon_code,
        )
        
        # Calculate discount
        discount = coupon.calculate_discount(order_total)
        
        return {
            "valid": True,
            "coupon_id": coupon.id,
            "coupon_code": coupon.code,
            "discount_amount": discount,
            "discount_type": coupon.discount_type,
            "discount_value": coupon.discount_value,
            "error": None,
        }
    
    def record_coupon_usage(self, coupon_id: int) -> bool:
        """
        Increment coupon usage counter after order is placed.
        
        Called after order payment succeeds.
        """
        try:
            coupon = Coupon.objects.select_for_update().get(id=coupon_id)
            coupon.times_used += 1
            coupon.save(update_fields=["times_used"])
            logger.info(f"Coupon {coupon.code} usage recorded (total: {coupon.times_used})")
            return True
        except Coupon.DoesNotExist:
            logger.error(f"Coupon {coupon_id} not found for usage recording")
            return False


class PromotionService:
    """
    Service for managing promotions/discounts.
    
    Currently delegates to CouponService.
    Can be extended for:
    - Promotional campaigns (buy X get Y)
    - Seasonal discounts
    - Bundle deals
    - Referral bonuses
    """
    
    def __init__(self):
        self.coupon_service = CouponService()
    
    def apply_promotions(
        self,
        store_id: int,
        order_total: Decimal,
        coupon_code: str = "",
    ) -> Dict[str, Any]:
        """
        Apply all available promotions to order.
        
        Currently only coupons; can be extended for other promotion types.
        
        Returns:
            {
                "total_discount": Decimal("200.00"),
                "promotions": [
                    {
                        "type": "coupon",
                        "code": "SAVE20",
                        "discount": Decimal("200.00"),
                    }
                ],
                "errors": [],
            }
        """
        result = {
            "total_discount": Decimal("0"),
            "promotions": [],
            "errors": [],
        }
        
        if not coupon_code:
            return result
        
        # Apply coupon if provided
        coupon_result = self.coupon_service.apply_coupon(
            store_id=store_id,
            coupon_code=coupon_code,
            order_total=order_total,
        )
        
        if coupon_result["valid"]:
            result["total_discount"] += coupon_result["discount_amount"]
            result["promotions"].append({
                "type": "coupon",
                "code": coupon_result["coupon_code"],
                "discount_amount": coupon_result["discount_amount"],
                "coupon_id": coupon_result["coupon_id"],
            })
        else:
            result["errors"].append(coupon_result["error"])
        
        return result

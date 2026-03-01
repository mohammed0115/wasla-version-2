from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from apps.coupons.models import Coupon, CouponUsageLog


class CouponValidationError(Exception):
    """Raised when coupon validation fails."""

    pass


class CouponValidationService:
    """Service to validate and apply coupons."""

    def validate_coupon(self, coupon, customer=None, subtotal=Decimal("0.00")):
        """
        Validate coupon for customer and amount.

        Returns:
            (bool, str) - (is_valid, error_message or "")
        """
        errors = []

        # Check if coupon is active
        if not coupon.is_active:
            errors.append("This coupon has been disabled")

        # Check dates
        now = timezone.now()
        if coupon.start_date > now:
            errors.append("This coupon is not yet active")
        if coupon.end_date < now:
            errors.append("This coupon has expired")

        # Check minimum purchase amount
        if subtotal < coupon.minimum_purchase_amount:
            errors.append(
                f"Minimum purchase amount of {coupon.minimum_purchase_amount} SAR required"
            )

        # Check global usage limit
        if coupon.usage_limit and coupon.times_used >= coupon.usage_limit:
            errors.append("This coupon has reached its usage limit")

        # Check per-customer usage limit
        if customer:
            customer_usage = CouponUsageLog.objects.filter(
                coupon=coupon,
                customer=customer,
            ).count()
            if customer_usage >= coupon.usage_limit_per_customer:
                errors.append(
                    f"You have already used this coupon {coupon.usage_limit_per_customer} time(s)"
                )

        if errors:
            return False, " | ".join(errors)

        return True, ""

    def apply_coupon(self, coupon, order, discount_amount):
        """
        Apply coupon to order and log usage.

        Args:
            coupon: Coupon instance
            order: Order instance
            discount_amount: Decimal amount of discount applied

        Returns:
            CouponUsageLog instance
        """
        with transaction.atomic():
            locked_coupon = (
                Coupon.objects.select_for_update()
                .filter(id=coupon.id)
                .first()
            )
            if not locked_coupon:
                raise CouponValidationError("Coupon not found.")

            if locked_coupon.usage_limit and locked_coupon.times_used >= locked_coupon.usage_limit:
                raise CouponValidationError("This coupon has reached its usage limit.")

            if order.customer and locked_coupon.usage_limit_per_customer:
                customer_usage = CouponUsageLog.objects.filter(
                    coupon=locked_coupon,
                    customer=order.customer,
                ).count()
                if customer_usage >= locked_coupon.usage_limit_per_customer:
                    raise CouponValidationError(
                        f"You have already used this coupon {locked_coupon.usage_limit_per_customer} time(s)."
                    )

            # Create usage log
            usage_log = CouponUsageLog.objects.create(
                coupon=locked_coupon,
                customer=order.customer,
                order=order,
                discount_applied=discount_amount,
            )

            # Increment coupon usage count atomically
            Coupon.objects.filter(id=locked_coupon.id).update(times_used=F("times_used") + 1)

        return usage_log

    def revoke_coupon_usage(self, order):
        """
        Revoke coupon usage for an order (e.g., if order is cancelled).

        Args:
            order: Order instance
        """
        usage_logs = CouponUsageLog.objects.filter(order=order)

        with transaction.atomic():
            for log in usage_logs:
                coupon = log.coupon
                Coupon.objects.filter(id=coupon.id, times_used__gt=0).update(times_used=F("times_used") - 1)
                log.delete()


class CouponAnalyticsService:
    """Service to analyze coupon usage and effectiveness."""

    def get_coupon_stats(self, coupon):
        """Get usage statistics for a coupon."""
        usage_logs = CouponUsageLog.objects.filter(coupon=coupon)

        total_discount = sum(
            log.discount_applied for log in usage_logs
        )

        return {
            "total_uses": coupon.times_used,
            "total_discount_applied": total_discount,
            "usage_percentage": (
                (coupon.times_used / coupon.usage_limit * 100)
                if coupon.usage_limit
                else None
            ),
            "average_discount": (
                total_discount / coupon.times_used if coupon.times_used > 0 else 0
            ),
            "is_active": coupon.is_active,
            "days_remaining": (coupon.end_date - timezone.now()).days,
        }

    def get_store_stats(self, store):
        """Get coupon usage stats for entire store."""
        coupons = Coupon.objects.filter(store=store)
        usage_logs = CouponUsageLog.objects.filter(coupon__in=coupons)

        return {
            "total_coupons": coupons.count(),
            "active_coupons": coupons.filter(is_active=True).count(),
            "total_discount": sum(
                log.discount_applied for log in usage_logs
            ),
            "total_uses": sum(c.times_used for c in coupons),
        }

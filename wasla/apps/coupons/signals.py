from django.db.models.signals import post_delete
from django.dispatch import receiver
from apps.coupons.models import CouponUsageLog
from apps.coupons.services import CouponValidationService


@receiver(post_delete, sender=CouponUsageLog)
def decrement_coupon_usage_on_log_delete(sender, instance, **kwargs):
    """
    Decrement coupon usage count when a usage log is deleted.
    (This is handled explicitly in CouponValidationService.revoke_coupon_usage)
    """
    pass

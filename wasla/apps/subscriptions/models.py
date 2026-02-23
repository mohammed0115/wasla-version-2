"""
Subscriptions models (MVP).

AR:
- تعريف خطط الاشتراك (Features + limits).
- ربط متجر بخطة عبر StoreSubscription.

EN:
- Defines subscription plans (features + limits).
- Links a store to a plan via StoreSubscription.
"""

from django.conf import settings
from django.db import models

from apps.tenants.managers import TenantManager


class SubscriptionPlan(models.Model):
    """A subscription plan with optional usage limits."""

    BILLING_CYCLE_CHOICES = [
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
    ]

    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    billing_cycle = models.CharField(
        max_length=20, choices=BILLING_CYCLE_CHOICES, default="monthly"
    )
    features = models.JSONField(default=list, blank=True)
    max_products = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Max products allowed for a store. Leave empty for unlimited.",
    )
    max_orders_monthly = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Max orders per calendar month for a store. Leave empty for unlimited.",
    )
    max_staff_users = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Max staff users allowed for a store. Leave empty for unlimited.",
    )
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class StoreSubscription(models.Model):
    """Subscription instance for a store."""
    objects = TenantManager()

    STATUS_CHOICES = [
        ("active", "Active"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
    ]

    store_id = models.IntegerField()
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, related_name="store_subscriptions"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Store {self.store_id} - {self.plan}"

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "status"]),
        ]


class PaymentTransaction(models.Model):
    """Manual (admin-recorded) payment for a subscription."""
    objects = TenantManager()

    METHOD_MANUAL = "manual"

    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="payment_transactions",
    )
    subscription = models.ForeignKey(
        StoreSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_transactions",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="payment_transactions",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="SAR")
    method = models.CharField(max_length=30, default=METHOD_MANUAL)
    reference = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_payment_transactions",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "status", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.plan_id} {self.amount} {self.status}"

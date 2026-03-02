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

    code = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="Stable plan code (e.g., free/basic/pro/enterprise).",
    )
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
    is_public = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    def __str__(self) -> str:
        return self.name


class PlanFeature(models.Model):
    """Feature flags or limits attached to a plan."""

    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.CASCADE, related_name="plan_features"
    )
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=150)
    is_enabled = models.BooleanField(default=True)
    limit_value = models.IntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("plan", "code"), name="uq_plan_feature_code"),
        ]
        indexes = [
            models.Index(fields=["plan", "code"]),
        ]

    def __str__(self) -> str:
        return f"{self.plan_id}:{self.code}"


class StoreSubscription(models.Model):
    """Subscription instance for a store."""
    objects = TenantManager()

    STATUS_ACTIVE = "active"
    STATUS_TRIAL = "trial"
    STATUS_PAST_DUE = "past_due"
    STATUS_CANCELED = "canceled"

    STATUS_EXPIRED = "expired"  # Legacy
    STATUS_CANCELLED = "cancelled"  # Legacy

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_TRIAL, "Trial"),
        (STATUS_PAST_DUE, "Past Due"),
        (STATUS_CANCELED, "Canceled"),
        (STATUS_EXPIRED, "Expired (Legacy)"),
        (STATUS_CANCELLED, "Cancelled (Legacy)"),
    ]

    store_id = models.IntegerField()
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, related_name="store_subscriptions"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    trial_ends_at = models.DateField(null=True, blank=True)
    current_period_end = models.DateField(null=True, blank=True)
    grace_until = models.DateField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

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

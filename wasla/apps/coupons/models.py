from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from apps.stores.models import Store
from apps.tenants.domain.models_mixins import TenantScopedModel


class CouponQuerySet(models.QuerySet):
    def active(self):
        """Filter for currently active coupons."""
        now = timezone.now()
        return self.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now,
        )

    def by_store(self, store):
        """Filter coupons for a specific store."""
        return self.filter(store=store)


class Coupon(TenantScopedModel):
    """Discount coupon for orders and products."""

    DISCOUNT_PERCENTAGE = "percentage"
    DISCOUNT_FIXED = "fixed"
    DISCOUNT_TYPES = [
        (DISCOUNT_PERCENTAGE, "Percentage Discount (%)"),
        (DISCOUNT_FIXED, "Fixed Amount Discount"),
    ]

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="coupons",
        help_text="Store this coupon belongs to",
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique coupon code (e.g., SAVE20)",
    )
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPES,
        default=DISCOUNT_PERCENTAGE,
        help_text="Type of discount",
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Discount amount or percentage",
    )
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Max discount cap for percentage coupons (e.g., max 50 SAR)",
    )
    minimum_purchase_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Minimum order value to use this coupon",
    )
    usage_limit = models.IntegerField(
        null=True,
        blank=True,
        help_text="Total uses allowed (null = unlimited)",
    )
    usage_limit_per_customer = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Uses per customer",
    )
    times_used = models.IntegerField(
        default=0,
        help_text="Current usage count",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Enable/disable coupon",
    )
    description = models.TextField(
        blank=True,
        help_text="Internal notes (not shown to customers)",
    )
    start_date = models.DateTimeField(
        default=timezone.now,
        help_text="When coupon becomes active",
    )
    end_date = models.DateTimeField(
        help_text="When coupon expires",
    )
    created_by = models.CharField(
        max_length=100,
        blank=True,
        help_text="Admin user who created coupon",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CouponQuerySet.as_manager()

    class Meta:
        db_table = "coupons_coupon"
        verbose_name = "Coupon"
        verbose_name_plural = "Coupons"
        indexes = [
            models.Index(fields=["store", "code"]),
            models.Index(fields=["store", "is_active"]),
            models.Index(fields=["end_date"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["store", "code"],
                name="unique_coupon_per_store",
            ),
        ]

    def __str__(self):
        return f"{self.code} - {self.get_discount_type_display()}"

    def is_valid_for_customer(self, customer=None):
        """Check if coupon is valid for a customer."""
        from apps.coupons.services import CouponValidationService

        service = CouponValidationService()
        return service.validate_coupon(self, customer)

    def calculate_discount(self, subtotal):
        """Calculate discount amount for given subtotal."""
        if self.discount_type == self.DISCOUNT_PERCENTAGE:
            discount = (subtotal * self.discount_value) / 100
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount)
            return discount
        else:  # FIXED
            return min(self.discount_value, subtotal)

    def has_usage_available(self, customer=None):
        """Check if coupon has usage available."""
        # Check global usage limit
        if self.usage_limit and self.times_used >= self.usage_limit:
            return False

        # Check per-customer limit
        if customer:
            customer_usage = CouponUsageLog.objects.filter(
                coupon=self,
                customer=customer,
            ).count()
            if customer_usage >= self.usage_limit_per_customer:
                return False

        return True


class CouponUsageLog(models.Model):
    """Track coupon usage per customer and order."""

    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name="usage_logs",
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Customer who used coupon (null for guests)",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="coupon_usage_logs",
        help_text="Order where coupon was applied",
    )
    discount_applied = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "coupons_usage_log"
        verbose_name = "Coupon Usage Log"
        verbose_name_plural = "Coupon Usage Logs"
        indexes = [
            models.Index(fields=["coupon", "customer"]),
            models.Index(fields=["used_at"]),
        ]

    def __str__(self):
        customer_str = self.customer or "Guest"
        return f"{self.coupon.code} - {customer_str} - Order #{self.order.id}"

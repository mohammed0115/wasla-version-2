"""
Shipping models.

AR: شحنات مرتبطة بالطلبات + مناطق الشحن + أسعار الشحن
EN: Shipments linked to orders + shipping zones + shipping rates
"""

from django.db import models
from django.core.validators import MinValueValidator

from apps.tenants.managers import TenantManager
from apps.stores.models import Store


class Shipment(models.Model):
    """Shipment record linked to an order."""
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"

    STATUS_CHOICES = [
        ("ready", "Ready"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="shipments"
    )
    carrier = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ready")
    tracking_number = models.CharField(max_length=100, blank=True, default="")
    notification_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.order} - {self.carrier}"


class ShippingZone(models.Model):
    """Geographic shipping zone for delivering to specific regions."""

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="shipping_zones",
        help_text="Store this zone belongs to",
    )
    name = models.CharField(
        max_length=100,
        help_text="Zone name (e.g., 'GCC Countries', 'Saudi Arabia')",
    )
    description = models.TextField(
        blank=True,
        help_text="Zone description and coverage areas",
    )
    countries = models.CharField(
        max_length=500,
        help_text="Comma-separated country codes (e.g., 'SA,AE,KW,QA')",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Enable/disable this zone",
    )
    priority = models.IntegerField(
        default=0,
        help_text="Priority for matching (higher number = higher priority)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "shipping_zone"
        verbose_name = "Shipping Zone"
        verbose_name_plural = "Shipping Zones"
        indexes = [
            models.Index(fields=["store", "is_active"]),
            models.Index(fields=["priority"]),
        ]
        ordering = ["-priority", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["store", "name"],
                name="unique_zone_per_store",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.store.name})"

    def get_countries_list(self):
        """Return list of country codes."""
        return [c.strip() for c in self.countries.split(",")]

    def covers_country(self, country_code):
        """Check if zone covers a country."""
        return country_code.upper() in [
            c.upper() for c in self.get_countries_list()
        ]


class ShippingRate(models.Model):
    """Shipping rate for a zone with weight-based or flat-rate options."""

    RATE_TYPE_FLAT = "flat"
    RATE_TYPE_WEIGHT = "weight"
    RATE_TYPES = [
        (RATE_TYPE_FLAT, "Flat Rate"),
        (RATE_TYPE_WEIGHT, "Weight-Based (per kg)"),
    ]

    zone = models.ForeignKey(
        ShippingZone,
        on_delete=models.CASCADE,
        related_name="shipping_rates",
        help_text="Zone this rate applies to",
    )
    name = models.CharField(
        max_length=100,
        help_text="Rate name (e.g., 'Standard', 'Express')",
    )
    rate_type = models.CharField(
        max_length=20,
        choices=RATE_TYPES,
        default=RATE_TYPE_FLAT,
        help_text="How shipping is calculated",
    )
    base_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Base shipping cost or cost per kg",
    )
    min_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Minimum weight for this rate (kg)",
    )
    max_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum weight for this rate (kg), null = no limit",
    )
    free_shipping_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Order amount for free shipping (e.g., 100 SAR)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Enable/disable this rate",
    )
    priority = models.IntegerField(
        default=0,
        help_text="Priority for matching (higher = first checked)",
    )
    estimated_days = models.IntegerField(
        null=True,
        blank=True,
        help_text="Estimated delivery days",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "shipping_rate"
        verbose_name = "Shipping Rate"
        verbose_name_plural = "Shipping Rates"
        indexes = [
            models.Index(fields=["zone", "is_active"]),
            models.Index(fields=["rate_type", "priority"]),
        ]
        ordering = ["-priority", "min_weight"]

    def __str__(self):
        return f"{self.name} - {self.zone.name}"

    def calculate_cost(self, weight, order_total):
        """
        Calculate shipping cost for weight and order total.

        Args:
            weight: Product weight in kg (Decimal)
            order_total: Order subtotal (Decimal)

        Returns:
            Decimal shipping cost
        """
        from decimal import Decimal
        
        # Check free shipping threshold
        if self.free_shipping_threshold and order_total >= self.free_shipping_threshold:
            return Decimal("0.00")

        # Check weight range
        if weight < self.min_weight:
            return None  # Rate doesn't apply
        if self.max_weight and weight > self.max_weight:
            return None  # Rate doesn't apply

        if self.rate_type == self.RATE_TYPE_FLAT:
            return self.base_rate
        else:  # WEIGHT
            return self.base_rate * weight

    def applies_to_weight(self, weight):
        """Check if this rate applies to weight."""
        if weight < self.min_weight:
            return False
        if self.max_weight and weight > self.max_weight:
            return False
        return True

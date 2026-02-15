"""
Payments models (MVP).

AR: يمثل عمليات الدفع المرتبطة بالطلبات (نجاح/فشل/قيد الانتظار).
EN: Represents payment attempts linked to orders (success/failed/pending).
"""

from django.db import models


class Payment(models.Model):
    """Payment record linked to an order."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="payments"
    )
    method = models.CharField(max_length=30)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.order} - {self.status}"


class PaymentIntent(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("requires_action", "Requires action"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
    ]

    store_id = models.IntegerField(db_index=True)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="payment_intents"
    )
    provider_code = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="SAR")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="pending")
    provider_reference = models.CharField(max_length=120, blank=True, default="")
    idempotency_key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "provider_code", "status"]),
            models.Index(fields=["provider_code", "provider_reference"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider_code}:{self.provider_reference or self.idempotency_key}"


class PaymentEvent(models.Model):
    provider_code = models.CharField(max_length=50)
    event_id = models.CharField(max_length=120)
    payload_json = models.JSONField(default=dict, blank=True)
    payload_raw = models.TextField(blank=True, default="")
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["provider_code", "event_id"]),
            models.Index(fields=["received_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider_code}:{self.event_id}"


class PaymentProviderSettings(models.Model):
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="payment_providers",
    )
    provider_code = models.CharField(max_length=50)
    display_name = models.CharField(max_length=120, blank=True, default="")
    is_enabled = models.BooleanField(default=False)
    credentials = models.JSONField(default=dict, blank=True)
    webhook_secret = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "provider_code"),
                name="uq_payment_provider_tenant_code",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_enabled"]),
            models.Index(fields=["provider_code", "is_enabled"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.provider_code}"

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
    """
    Multi-tenant payment provider configuration.
    Stores provider API keys, webhook secrets, and fee settings per tenant.
    """
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
    
    # Fee configuration per provider per tenant
    transaction_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Transaction fee percentage (e.g., 2.50 for 2.5%)"
    )
    wasla_commission_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=3,
        help_text="Wasla platform commission percentage"
    )
    is_sandbox_mode = models.BooleanField(default=True)
    
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


class RefundRecord(models.Model):
    """
    Refund record linked to a payment.
    Tracks refund attempts and status.
    """
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_FAILED, "Failed"),
    ]

    payment_intent = models.ForeignKey(
        PaymentIntent, on_delete=models.PROTECT, related_name="refunds"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="SAR")
    provider_reference = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reason = models.TextField(blank=True, default="")
    raw_response = models.JSONField(default=dict, blank=True)
    requested_by = models.CharField(max_length=120, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["payment_intent", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"Refund {self.id} - {self.amount} {self.currency}"

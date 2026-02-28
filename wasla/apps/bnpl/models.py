"""BNPL Models for Tabby and Tamara integration."""

from django.db import models
from django.core.validators import MinValueValidator
from apps.stores.models import Store
from apps.orders.models import Order


class BnplProvider(models.Model):
    """Store BNPL provider settings (Tabby, Tamara, etc.)."""

    PROVIDER_TABBY = "tabby"
    PROVIDER_TAMARA = "tamara"
    PROVIDER_CHOICES = [
        (PROVIDER_TABBY, "Tabby"),
        (PROVIDER_TAMARA, "Tamara"),
    ]

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="bnpl_providers",
    )
    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
    )
    api_key = models.CharField(
        max_length=255,
        help_text="Provider API key (encrypted in production)",
    )
    secret_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="Provider secret key if required",
    )
    merchant_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Merchant ID for the provider",
    )
    is_active = models.BooleanField(default=True)
    is_sandbox = models.BooleanField(
        default=True,
        help_text="Sandbox mode for testing",
    )
    webhook_secret = models.CharField(
        max_length=255,
        blank=True,
        help_text="Webhook signing secret for verification",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bnpl_provider"
        verbose_name = "BNPL Provider"
        verbose_name_plural = "BNPL Providers"
        unique_together = [["store", "provider"]]
        indexes = [
            models.Index(fields=["store", "is_active"]),
            models.Index(fields=["provider"]),
        ]

    def __str__(self):
        return f"{self.store.name} - {self.get_provider_display()}"

    def get_api_url(self):
        """Get API URL based on provider and mode."""
        if self.provider == self.PROVIDER_TABBY:
            return (
                "https://api.tabby.ai"
                if not self.is_sandbox
                else "https://api.staging.tabby.ai"
            )
        elif self.provider == self.PROVIDER_TAMARA:
            return (
                "https://api.tamara.co"
                if not self.is_sandbox
                else "https://api-sandbox.tamara.co"
            )
        return None


class BnplTransaction(models.Model):
    """Track BNPL transactions (payments made through Tabby/Tamara)."""

    STATUS_PENDING = "pending"
    STATUS_AUTHORIZED = "authorized"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"
    STATUS_PAID = "paid"
    STATUS_REFUNDED = "refunded"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_AUTHORIZED, "Authorized"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_PAID, "Paid"),
        (STATUS_REFUNDED, "Refunded"),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="bnpl_transaction",
    )
    provider = models.CharField(
        max_length=20,
        choices=BnplProvider.PROVIDER_CHOICES,
    )
    provider_order_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="Order ID from provider (Tabby/Tamara)",
    )
    provider_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Additional reference from provider",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField(max_length=3, default="SAR")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    installment_count = models.IntegerField(
        default=3,
        help_text="Number of installments",
    )
    installment_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20, blank=True)
    payment_url = models.URLField(
        blank=True,
        help_text="URL customer redirects to for payment",
    )
    checkout_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Checkout session ID from provider",
    )
    response_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Full response from provider API",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bnpl_transaction"
        verbose_name = "BNPL Transaction"
        verbose_name_plural = "BNPL Transactions"
        indexes = [
            models.Index(fields=["order", "provider"]),
            models.Index(fields=["provider_order_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Order #{self.order.id} - {self.get_provider_display()}"

    def is_paid(self):
        """Check if transaction is paid."""
        return self.status in [self.STATUS_PAID, self.STATUS_APPROVED]

    def is_pending(self):
        """Check if transaction is waiting for customer action."""
        return self.status in [self.STATUS_PENDING, self.STATUS_AUTHORIZED]


class BnplWebhookLog(models.Model):
    """Log webhook events from BNPL providers for auditing."""

    transaction = models.ForeignKey(
        BnplTransaction,
        on_delete=models.CASCADE,
        related_name="webhook_logs",
    )
    event_type = models.CharField(
        max_length=50,
        help_text="e.g., payment.approved, payment.rejected",
    )
    status = models.CharField(
        max_length=20,
        help_text="Status from webhook",
    )
    payload = models.JSONField(
        help_text="Full webhook payload",
    )
    signature_verified = models.BooleanField(
        default=False,
        help_text="Whether signature was valid",
    )
    processed = models.BooleanField(
        default=False,
        help_text="Whether webhook was processed",
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error if processing failed",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bnpl_webhook_log"
        verbose_name = "BNPL Webhook Log"
        verbose_name_plural = "BNPL Webhook Logs"
        indexes = [
            models.Index(fields=["transaction", "event_type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.transaction} - {self.event_type}"

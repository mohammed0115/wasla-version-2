"""
Payments models (MVP).

AR: يمثل عمليات الدفع المرتبطة بالطلبات (نجاح/فشل/قيد الانتظار).
EN: Represents payment attempts linked to orders (success/failed/pending).
"""

from django.db import models

from apps.tenants.managers import TenantManager


class Payment(models.Model):
    """Payment record linked to an order."""
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
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
    objects = TenantManager()
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("requires_action", "Requires action"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
    ]

    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
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
    risk_score = models.IntegerField(default=0, help_text="Risk score 0-100, higher is riskier")
    is_flagged = models.BooleanField(default=False, db_index=True, help_text="Flagged for manual review")
    fraud_checks = models.JSONField(default=dict, blank=True, help_text="Fraud check results")
    attempt_count = models.IntegerField(default=0, help_text="Number of payment attempts")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "provider_code", "status"]),
            models.Index(fields=["provider_code", "provider_reference"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider_code}:{self.provider_reference or self.idempotency_key}"


class PaymentAttempt(models.Model):
    """Unified store-scoped payment attempt for provider orchestration."""

    PROVIDER_TAP = "tap"
    PROVIDER_STRIPE = "stripe"
    PROVIDER_PAYPAL = "paypal"

    PROVIDER_CHOICES = [
        (PROVIDER_TAP, "Tap"),
        (PROVIDER_STRIPE, "Stripe"),
        (PROVIDER_PAYPAL, "PayPal"),
    ]

    STATUS_INITIATED = "initiated"
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_FAILED = "failed"
    STATUS_REFUNDED = "refunded"
    STATUS_FLAGGED = "flagged"
    STATUS_RETRY_PENDING = "retry_pending"

    # Backward compatibility aliases
    STATUS_CREATED = STATUS_INITIATED
    STATUS_PAID = STATUS_CONFIRMED
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_INITIATED, "Initiated"),
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_REFUNDED, "Refunded"),
        (STATUS_FLAGGED, "Flagged"),
        (STATUS_RETRY_PENDING, "Retry Pending"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    store = models.ForeignKey(
        "stores.Store", on_delete=models.CASCADE, related_name="payment_attempts"
    )
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="payment_attempts"
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    method = models.CharField(max_length=30)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="SAR")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_INITIATED)
    provider_reference = models.CharField(max_length=120, blank=True, default="")
    idempotency_key = models.CharField(max_length=128, db_index=True)
    raw_response = models.JSONField(default=dict, blank=True)
    risk_score = models.IntegerField(default=0)
    is_flagged = models.BooleanField(default=False, db_index=True)
    
    # Security enhancements
    retry_count = models.IntegerField(
        default=0,
        help_text="Number of retry attempts"
    )
    last_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last retry"
    )
    next_retry_after = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When to retry next (exponential backoff)"
    )
    retry_pending = models.BooleanField(
        default=False,
        help_text="Waiting for retry after timeout"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Customer IP address from request"
    )
    user_agent = models.TextField(
        blank=True,
        default="",
        help_text="User agent from client request"
    )
    webhook_received = models.BooleanField(
        default=False,
        help_text="Webhook confirmation received"
    )
    webhook_verified = models.BooleanField(
        default=False,
        help_text="Webhook signature verified"
    )
    webhook_event = models.ForeignKey(
        "WebhookEvent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_attempts",
        help_text="Webhook that confirmed this payment"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("store", "order", "idempotency_key"),
                name="uq_payment_attempt_store_order_idempotency",
            ),
        ]
        indexes = [
            models.Index(fields=["store", "provider", "status"]),
            models.Index(fields=["provider", "provider_reference"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.provider_reference or self.idempotency_key}"


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


class WebhookEvent(models.Model):
    """
    Webhook event with enterprise security (replay protection, signature validation).
    
    Implements:
    - HMAC SHA256 signature validation
    - Event ID deduplication (replay protection)
    - Payload hash for integrity
    - Structured audit trail
    """
    STATUS_RECEIVED = "received"
    STATUS_PROCESSING = "processing"
    STATUS_IGNORED = "ignored"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_RECEIVED, "Received"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_IGNORED, "Ignored"),
        (STATUS_PROCESSED, "Processed"),
        (STATUS_FAILED, "Failed"),
    ]

    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.CASCADE,
        related_name="webhook_events",
        null=True,
        blank=True,
    )
    provider = models.CharField(max_length=20, db_index=True)
    provider_name = models.CharField(max_length=50, blank=True, default="")
    event_id = models.CharField(max_length=120, db_index=True)
    received_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(default=dict, blank=True)
    raw_payload = models.TextField(blank=True, default="")
    payload_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="SHA256 hash of payload for integrity"
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RECEIVED,
        db_index=True
    )
    signature = models.CharField(max_length=255, blank=True, default="")
    signature_verified = models.BooleanField(default=False, db_index=True)
    signature_valid = models.BooleanField(default=False, db_index=True)
    processed = models.BooleanField(default=False, db_index=True)
    webhook_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Provider timestamp from webhook"
    )
    timestamp_tolerance_seconds = models.IntegerField(
        default=300,
        help_text="Tolerance for timestamp validation (5 min default)"
    )
    retry_count = models.IntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    idempotency_checked = models.BooleanField(
        default=False,
        help_text="Whether idempotency was verified"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("store", "event_id"),
                name="uq_payment_webhook_store_event",
            ),
        ]
        indexes = [
            models.Index(fields=["provider", "event_id"]),
            models.Index(fields=["status", "received_at"]),
            models.Index(fields=["signature_verified", "status"]),
            models.Index(fields=["store", "provider", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.event_id} ({self.status})"


class PaymentProviderSettings(models.Model):
    """
    Multi-tenant payment provider configuration.
    Stores provider API keys, webhook secrets, and fee settings per tenant.
    """
    PROVIDER_CHOICES = [
        ("tap", "Tap"),
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
    ]
    MODE_CHOICES = [
        ("sandbox", "Sandbox"),
        ("prod", "Production"),
    ]

    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.CASCADE,
        related_name="payment_provider_settings",
        null=True,
        blank=True,
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="payment_providers",
    )
    objects = TenantManager()
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, blank=True, default="")
    public_key = models.CharField(max_length=255, blank=True, default="")
    secret_key = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=False)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default="sandbox")
    provider_code = models.CharField(max_length=50)
    display_name = models.CharField(max_length=120, blank=True, default="")
    is_enabled = models.BooleanField(default=False)
    credentials = models.JSONField(default=dict, blank=True)
    webhook_secret = models.CharField(max_length=255, blank=True, default="")
    webhook_tolerance_seconds = models.IntegerField(default=300)
    retry_max_attempts = models.IntegerField(default=3)
    
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
            models.UniqueConstraint(
                fields=("store", "provider"),
                name="uq_payment_provider_store_code",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_enabled"]),
            models.Index(fields=["provider_code", "is_enabled"]),
            models.Index(fields=["store", "provider", "is_active"]),
        ]

    def __str__(self) -> str:
        provider_key = self.provider or self.provider_code
        owner_key = self.store_id or self.tenant_id
        return f"{owner_key}:{provider_key}"


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

    objects = TenantManager()
    TENANT_FIELD = "tenant_id"
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
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


class ProviderCommunicationLog(models.Model):
    """Structured log of all provider API communication for debugging and compliance."""
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"

    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    provider_code = models.CharField(max_length=50)
    operation = models.CharField(max_length=100, help_text="initiate_payment, verify_callback, refund")
    request_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True, default=None)
    duration_ms = models.IntegerField(null=True, blank=True, help_text="Request duration in ms")
    attempt_number = models.IntegerField(default=1)
    idempotency_key = models.CharField(max_length=120, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["provider_code", "operation", "created_at"]),
            models.Index(fields=["tenant_id", "created_at"]),
            models.Index(fields=["idempotency_key"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider_code}:{self.operation}#{self.attempt_number}"

class PaymentRisk(models.Model):
    """
    Risk assessment and flagging for payment attempts.
    
    Fraud detection:
    - IP velocity scoring
    - Amount velocity
    - Refund rate analysis
    - Custom risk rules
    
    Flagged payments require manual approval before settlement.
    """
    
    RISK_LEVEL_LOW = "low"
    RISK_LEVEL_MEDIUM = "medium"
    RISK_LEVEL_HIGH = "high"
    RISK_LEVEL_CRITICAL = "critical"
    
    RISK_LEVEL_CHOICES = [
        (RISK_LEVEL_LOW, "Low (0-25)"),
        (RISK_LEVEL_MEDIUM, "Medium (26-50)"),
        (RISK_LEVEL_HIGH, "High (51-75)"),
        (RISK_LEVEL_CRITICAL, "Critical (76-100)"),
    ]
    
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"
    
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.CASCADE,
        related_name="payment_risks",
        null=True,
        blank=True,
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="payment_risks",
    )
    payment_attempt = models.OneToOneField(
        PaymentAttempt,
        on_delete=models.CASCADE,
        related_name="risk_assessment",
        null=True,
        blank=True,
    )
    
    # Risk scoring (0-100)
    risk_score = models.IntegerField(
        default=0,
        help_text="Total risk score 0-100"
    )
    risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        default=RISK_LEVEL_LOW,
        db_index=True,
    )
    flagged = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flagged for manual review"
    )
    
    # Velocity metrics
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Customer IP address"
    )
    velocity_count_5min = models.IntegerField(
        default=0,
        help_text="Payments from same IP in last 5 minutes"
    )
    velocity_count_1hour = models.IntegerField(
        default=0,
        help_text="Payments from same IP in last 1 hour"
    )
    velocity_amount_5min = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Total amount from same IP in last 5 minutes"
    )
    
    # Risk factors
    refund_rate_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Historical refund rate for this customer"
    )
    previous_failed_attempts = models.IntegerField(
        default=0,
        help_text="Count of failed payment attempts"
    )
    is_new_customer = models.BooleanField(
        default=False,
        help_text="Customer's first purchase"
    )
    unusual_amount = models.BooleanField(
        default=False,
        help_text="Amount significantly higher than average"
    )
    
    # Risk rules triggered
    triggered_rules = models.JSONField(
        default=list,
        blank=True,
        help_text="List of risk rules that triggered"
    )
    
    # Review status
    reviewed = models.BooleanField(default=False, db_index=True)
    reviewed_by = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Admin user who reviewed this"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_decision = models.CharField(
        max_length=20,
        choices=[
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("pending", "Pending"),
        ],
        default="pending",
    )
    review_notes = models.TextField(blank=True, default="")
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["store", "flagged", "created_at"]),
            models.Index(fields=["risk_level", "reviewed"]),
            models.Index(fields=["ip_address", "created_at"]),
            models.Index(fields=["order"]),
        ]
        ordering = ["-risk_score", "-created_at"]
    
    def __str__(self) -> str:
        return f"Risk({self.order_id}) {self.risk_level}:{self.risk_score}"
    
    @property
    def is_critical(self) -> bool:
        """Whether risk is critical and requires immediate review."""
        return self.risk_score >= 76 or self.flagged
    
    @property
    def needs_review(self) -> bool:
        """Whether payment needs manual review."""
        return self.flagged and not self.reviewed
"""
Advanced SaaS Billing Models for Wassla Subscriptions.

Implements:
- Subscription state machine (active, past_due, grace, suspended, cancelled)
- Billing cycles and invoices
- Dunning management (retry tracking)
- Payment methods and events
- Proration for upgrades/downgrades
"""

from django.db import models
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta, datetime
import uuid

from apps.tenants.managers import TenantManager


class Subscription(models.Model):
    """
    Full-featured subscription with state machine.
    Tracks the complete lifecycle of a tenant's subscription.
    """
    
    STATE_CHOICES = [
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('grace', 'Grace Period'),
        ('suspended', 'Suspended'),
        ('cancelled', 'Cancelled'),
    ]
    
    objects = TenantManager()
    
    # Identifiers
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='subscription'
    )
    
    # Plan and pricing
    plan = models.ForeignKey(
        'BillingPlan',
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )
    
    # Billing details
    currency = models.CharField(max_length=3, default='SAR')
    billing_cycle_anchor = models.DateField(
        help_text='Day of month when billing cycle renews (1-28)'
    )
    next_billing_date = models.DateField()
    
    # State machine
    state = models.CharField(
        max_length=20,
        choices=STATE_CHOICES,
        default='active'
    )
    
    # Grace period
    grace_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Extends deadline for payment if set'
    )
    
    # Suspension
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.CharField(max_length=255, blank=True)
    
    # Lifecycle
    started_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, blank=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscriptions_subscription'
        indexes = [
            models.Index(fields=['tenant', 'state']),
            models.Index(fields=['state', 'next_billing_date']),
        ]
    
    def __str__(self):
        return f"{self.tenant} - {self.plan.name} ({self.state})"
    
    def is_active(self):
        """Check if subscription is in active state."""
        return self.state == 'active'
    
    def is_suspended(self):
        """Check if subscription is suspended."""
        return self.state == 'suspended'
    
    def is_past_due(self):
        """Check if subscription is past due."""
        return self.state == 'past_due'
    
    def can_use_service(self):
        """Check if merchant can use service (not suspended)."""
        return self.state in ['active', 'past_due', 'grace']


class SubscriptionItem(models.Model):
    """
    Line items for usage-based or metered billing.
    Allows subscriptions to have multiple billable items.
    """
    
    BILLING_TYPE_CHOICES = [
        ('fixed', 'Fixed'),
        ('usage', 'Usage-based'),
        ('metered', 'Metered'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='items'
    )
    
    # Item details
    name = models.CharField(max_length=255)
    billing_type = models.CharField(
        max_length=20,
        choices=BILLING_TYPE_CHOICES,
        default='fixed'
    )
    
    # Pricing
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='SAR')
    
    # Usage tracking (for usage/metered items)
    current_usage = models.PositiveIntegerField(default=0)
    usage_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Max usage per billing cycle'
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscriptions_subscription_item'
    
    def __str__(self):
        return f"{self.subscription.tenant} - {self.name}"
    
    def has_exceeded_usage(self):
        """Check if usage has exceeded limit."""
        if not self.usage_limit:
            return False
        return self.current_usage >= self.usage_limit


class BillingCycle(models.Model):
    """
    Represents a single billing period for a subscription.
    One per subscription per month (or billing interval).
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('billed', 'Billed'),
        ('partial', 'Partial Payment'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='billing_cycles'
    )
    
    # Period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Amounts
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Proration
    proration_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    proration_reason = models.CharField(max_length=255, blank=True)
    
    # Billing
    invoice_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    
    # Lifecycle
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscriptions_billing_cycle'
        ordering = ['-period_end']
        indexes = [
            models.Index(fields=['subscription', 'period_end']),
            models.Index(fields=['status', 'due_date']),
        ]
    
    def __str__(self):
        return f"{self.subscription.tenant} - {self.period_start} to {self.period_end}"
    
    def is_overdue(self):
        """Check if billing cycle is overdue."""
        if not self.due_date:
            return False
        return timezone.now().date() > self.due_date


class Invoice(models.Model):
    """
    Invoice document for a billing cycle.
    Can be paid partially or completely.
    """
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('overdue', 'Overdue'),
        ('partial', 'Partial Payment'),
        ('paid', 'Paid'),
        ('void', 'Void'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=50, unique=True, db_index=True)
    
    billing_cycle = models.OneToOneField(
        BillingCycle,
        on_delete=models.CASCADE,
        related_name='invoice'
    )
    
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='invoices'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    
    # Amounts
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Payment tracking
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Dates
    issued_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    
    # Idempotency
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text='Ensures invoice is only created once'
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscriptions_invoice'
        ordering = ['-issued_date']
        indexes = [
            models.Index(fields=['subscription', 'status']),
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['number']),
        ]
    
    def __str__(self):
        return f"Invoice {self.number} - {self.subscription.tenant}"
    
    def is_overdue(self):
        """Check if invoice is overdue."""
        if self.status in ['paid', 'void']:
            return False
        return timezone.now().date() > self.due_date


class DunningAttempt(models.Model):
    """
    Tracks payment retry attempts (dunning).
    Used for exponential backoff and limiting retries.
    """
    
    STRATEGY_CHOICES = [
        ('immediate', 'Immediate Retry'),
        ('incremental', 'Incremental Retry'),
        ('exponential', 'Exponential Backoff'),
    ]
    
    ATTEMPT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='dunning_attempts'
    )
    
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='dunning_attempts'
    )
    
    # Attempt details
    attempt_number = models.PositiveIntegerField(default=1)
    strategy = models.CharField(
        max_length=20,
        choices=STRATEGY_CHOICES,
        default='exponential'
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=ATTEMPT_STATUS_CHOICES,
        default='pending'
    )
    
    # Retry scheduling
    scheduled_for = models.DateTimeField()
    attempted_at = models.DateTimeField(null=True, blank=True)
    
    # Result
    error_message = models.TextField(blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    
    # Next retry
    next_retry_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscriptions_dunning_attempt'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invoice', 'status']),
            models.Index(fields=['subscription', 'status']),
            models.Index(fields=['status', 'scheduled_for']),
        ]
    
    def __str__(self):
        return f"Dunning {self.invoice.number} - Attempt {self.attempt_number}"
    
    def is_due(self):
        """Check if retry is due for execution."""
        return self.status == 'pending' and timezone.now() >= self.scheduled_for


class PaymentEvent(models.Model):
    """
    Webhook event from payment provider.
    Used for syncing payment status and idempotent processing.
    """
    
    EVENT_TYPES = [
        ('payment.succeeded', 'Payment Succeeded'),
        ('payment.failed', 'Payment Failed'),
        ('invoice.paid', 'Invoice Paid'),
        ('invoice.payment_failed', 'Invoice Payment Failed'),
        ('customer.subscription.updated', 'Subscription Updated'),
    ]
    
    STATUS_CHOICES = [
        ('received', 'Received'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Event details
    event_type = models.CharField(
        max_length=50,
        choices=EVENT_TYPES
    )
    
    provider_event_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text='External ID from payment provider (idempotency key)'
    )
    
    # Payload
    payload = models.JSONField(
        help_text='Full webhook payload from provider'
    )
    
    # Processing
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='received'
    )
    
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Related objects
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='payment_events'
    )
    
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='payment_events'
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'subscriptions_payment_event'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider_event_id']),
            models.Index(fields=['subscription', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.provider_event_id}"


class PaymentMethod(models.Model):
    """
    Payment method registered for a subscription (credit card, bank account, etc).
    """
    
    METHOD_TYPE_CHOICES = [
        ('card', 'Credit/Debit Card'),
        ('bank', 'Bank Account'),
        ('wallet', 'Digital Wallet'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('expired', 'Expired'),
        ('invalid', 'Invalid'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.OneToOneField(
        Subscription,
        on_delete=models.CASCADE,
        related_name='payment_method'
    )
    
    # Method details
    method_type = models.CharField(
        max_length=20,
        choices=METHOD_TYPE_CHOICES,
        default='card'
    )
    
    # Customer token from provider
    provider_customer_id = models.CharField(
        max_length=255,
        help_text='Customer ID from payment provider'
    )
    
    provider_payment_method_id = models.CharField(
        max_length=255,
        help_text='Payment method ID from payment provider'
    )
    
    # Display info
    display_name = models.CharField(
        max_length=255,
        blank=True,
        help_text='e.g., Last 4 digits, bank name'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    
    # Dates
    added_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscriptions_payment_method'
    
    def __str__(self):
        return f"{self.subscription.tenant} - {self.display_name}"
    
    def is_valid(self):
        """Check if payment method is valid and not expired."""
        if self.status != 'active':
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True


class BillingPlan(models.Model):
    """
    Subscription plan definition with features and pricing.
    Extended from original lightweight model.
    """
    
    BILLING_CYCLE_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('quarterly', 'Quarterly'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic info
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Pricing
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='SAR')
    
    billing_cycle = models.CharField(
        max_length=20,
        choices=BILLING_CYCLE_CHOICES,
        default='monthly'
    )
    
    # Features
    features = models.JSONField(default=list, blank=True)
    
    # Usage limits
    max_products = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Max products allowed. Null = unlimited.'
    )
    
    max_orders_monthly = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Max orders per month. Null = unlimited.'
    )
    
    max_staff_users = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Max staff users. Null = unlimited.'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscriptions_subscription_plan'
    
    def __str__(self):
        return f"{self.name} ({self.currency} {self.price}/{self.get_billing_cycle_display()})"

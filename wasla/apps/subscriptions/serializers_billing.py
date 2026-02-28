"""
API Serializers for SaaS billing system.

Handles serialization of:
- Subscriptions
- Billing cycles
- Invoices
- Dunning attempts
- Payment methods
- Payment events
"""

from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone

from .models_billing import (
    Subscription, SubscriptionItem, BillingCycle, Invoice,
    DunningAttempt, PaymentEvent, PaymentMethod, BillingPlan
)


class BillingPlanSerializer(serializers.ModelSerializer):
    """Serializer for billing plans."""
    
    class Meta:
        model = BillingPlan
        fields = [
            'id', 'name', 'description', 'price', 'currency',
            'billing_cycle', 'features', 'max_products',
            'max_orders_monthly', 'max_staff_users', 'is_active'
        ]
        read_only_fields = ['id']


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for payment methods."""
    
    is_valid = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'method_type', 'display_name', 'status',
            'added_at', 'expires_at', 'last_used_at', 'is_valid'
        ]
        read_only_fields = [
            'id', 'added_at', 'last_used_at', 'provider_customer_id',
            'provider_payment_method_id'
        ]
    
    def get_is_valid(self, obj):
        return obj.is_valid()


class SubscriptionItemSerializer(serializers.ModelSerializer):
    """Serializer for subscription line items."""
    
    has_exceeded_usage = serializers.SerializerMethodField()
    
    class Meta:
        model = SubscriptionItem
        fields = [
            'id', 'subscription', 'name', 'billing_type',
            'price', 'currency', 'current_usage', 'usage_limit',
            'has_exceeded_usage', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_has_exceeded_usage(self, obj):
        return obj.has_exceeded_usage()


class BillingCycleSerializer(serializers.ModelSerializer):
    """Serializer for billing cycles."""
    
    is_overdue = serializers.SerializerMethodField()
    days_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = BillingCycle
        fields = [
            'id', 'subscription', 'period_start', 'period_end',
            'status', 'subtotal', 'discount', 'tax', 'total',
            'proration_total', 'proration_reason',
            'invoice_date', 'due_date', 'is_overdue', 'days_overdue',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'subtotal', 'discount', 'tax', 'total',
            'created_at', 'updated_at'
        ]
    
    def get_is_overdue(self, obj):
        return obj.is_overdue()
    
    def get_days_overdue(self, obj):
        if not obj.is_overdue():
            return 0
        return (timezone.now().date() - obj.due_date).days


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer for invoices."""
    
    is_overdue = serializers.SerializerMethodField()
    days_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'number', 'billing_cycle', 'subscription',
            'status', 'subtotal', 'tax', 'discount', 'total',
            'amount_paid', 'amount_due', 'issued_date', 'due_date',
            'paid_date', 'is_overdue', 'days_overdue',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'number', 'created_at', 'updated_at',
            'subtotal', 'tax', 'discount', 'total'
        ]
    
    def get_is_overdue(self, obj):
        return obj.is_overdue()
    
    def get_days_overdue(self, obj):
        if not obj.is_overdue():
            return 0
        return (timezone.now().date() - obj.due_date).days


class DunningAttemptSerializer(serializers.ModelSerializer):
    """Serializer for dunning attempts."""
    
    is_due = serializers.SerializerMethodField()
    
    class Meta:
        model = DunningAttempt
        fields = [
            'id', 'invoice', 'subscription', 'attempt_number',
            'strategy', 'status', 'scheduled_for', 'attempted_at',
            'error_message', 'error_code', 'next_retry_at',
            'is_due', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'attempt_number', 'attempted_at',
            'created_at', 'updated_at'
        ]
    
    def get_is_due(self, obj):
        return obj.is_due()


class PaymentEventSerializer(serializers.ModelSerializer):
    """Serializer for payment events."""
    
    class Meta:
        model = PaymentEvent
        fields = [
            'id', 'event_type', 'provider_event_id', 'status',
            'subscription', 'invoice', 'processed_at',
            'error_message', 'created_at'
        ]
        read_only_fields = [
            'id', 'processed_at', 'created_at'
        ]


class SubscriptionCreateSerializer(serializers.Serializer):
    """Serializer for creating a new subscription."""
    
    plan_id = serializers.UUIDField()
    payment_method_id = serializers.UUIDField()
    billing_cycle_anchor = serializers.IntegerField(min_value=1, max_value=28, default=1)
    
    def validate_plan_id(self, value):
        try:
            SubscriptionPlan.objects.get(id=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Plan not found or inactive")
        return value
    
    def validate_payment_method_id(self, value):
        try:
            PaymentMethod.objects.get(id=value)
        except PaymentMethod.DoesNotExist:
            raise serializers.ValidationError("Payment method not found")
        return value


class SubscriptionDetailSerializer(serializers.ModelSerializer):
    """Detailed subscription serializer with related data."""
    
    plan = BillingPlanSerializer(read_only=True)
    payment_method = PaymentMethodSerializer(read_only=True)
    items = SubscriptionItemSerializer(many=True, read_only=True)
    
    can_use_service = serializers.SerializerMethodField()
    days_until_billing = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'tenant', 'plan', 'currency', 'billing_cycle_anchor',
            'next_billing_date', 'state', 'grace_until', 'suspended_at',
            'suspension_reason', 'started_at', 'cancelled_at',
            'cancellation_reason', 'payment_method', 'items',
            'can_use_service', 'days_until_billing',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'created_at', 'updated_at',
            'started_at', 'cancelled_at', 'suspended_at'
        ]
    
    def get_can_use_service(self, obj):
        return obj.can_use_service()
    
    def get_days_until_billing(self, obj):
        delta = (obj.next_billing_date - timezone.now().date()).days
        return max(0, delta)


class SubscriptionListSerializer(serializers.ModelSerializer):
    """Simplified subscription serializer for list views."""
    
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_price = serializers.DecimalField(
        source='plan.price',
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    
    can_use_service = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'tenant', 'plan_name', 'plan_price', 'currency',
            'next_billing_date', 'state', 'can_use_service',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_can_use_service(self, obj):
        return obj.can_use_service()


class SubscriptionChangeSerializer(serializers.Serializer):
    """Serializer for plan change request."""
    
    new_plan_id = serializers.UUIDField()
    
    def validate_new_plan_id(self, value):
        try:
            SubscriptionPlan.objects.get(id=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Plan not found or inactive")
        return value


class SubscriptionCancelSerializer(serializers.Serializer):
    """Serializer for subscription cancellation."""
    
    reason = serializers.CharField(required=False, allow_blank=True)
    immediately = serializers.BooleanField(default=False)


class PaymentMethodCreateSerializer(serializers.Serializer):
    """Serializer for creating a payment method."""
    
    method_type = serializers.ChoiceField(
        choices=PaymentMethod.METHOD_TYPE_CHOICES
    )
    
    # These would come from payment provider tokenization
    provider_customer_id = serializers.CharField()
    provider_payment_method_id = serializers.CharField()
    display_name = serializers.CharField()


class GracePeriodSerializer(serializers.Serializer):
    """Serializer for adding grace period."""
    
    days = serializers.IntegerField(min_value=1, max_value=30, default=7)


class DunningRetrySerializer(serializers.Serializer):
    """Serializer for manually triggering dunning retry."""
    
    invoice_id = serializers.UUIDField()


class WebhookPayloadSerializer(serializers.Serializer):
    """Serializer for incoming webhook payloads."""
    
    event_type = serializers.CharField()
    provider_event_id = serializers.CharField()
    payload = serializers.JSONField()


# ============================================================================
# Response Serializers
# ============================================================================

class BillingStatusSerializer(serializers.Serializer):
    """Multi-purpose response for billing status."""
    
    subscription_state = serializers.CharField()
    next_billing_date = serializers.DateField()
    outstanding_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2
    )
    currency = serializers.CharField()
    is_active = serializers.BooleanField()
    grace_until = serializers.DateTimeField(allow_null=True)
    action_required = serializers.BooleanField()


class ProrateCalculationSerializer(serializers.Serializer):
    """Response for proration calculation."""
    
    old_plan = serializers.CharField()
    new_plan = serializers.CharField()
    proration_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    proration_type = serializers.CharField()  # 'credit' or 'charge'
    effective_date = serializers.DateField()


class DunningStatusSerializer(serializers.Serializer):
    """Response for dunning status."""
    
    invoice_id = serializers.CharField()
    invoice_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    current_attempt = serializers.IntegerField()
    next_retry_date = serializers.DateTimeField(allow_null=True)
    last_error = serializers.CharField()
    status = serializers.CharField()

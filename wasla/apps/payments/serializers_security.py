"""
Django REST Framework serializers for payment security endpoints.

Provides:
- Read-only payment timeline for merchants
- Full admin access to payment events and risk queue
- Risk approval/rejection workflows
"""

from rest_framework import serializers
from django.utils import timezone

from apps.payments.models import (
    PaymentAttempt,
    WebhookEvent,
    PaymentRisk,
    PaymentProviderSettings,
)
from apps.orders.models import Order


class PaymentRiskSerializer(serializers.ModelSerializer):
    """Serializer for PaymentRisk with review workflow."""
    
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer_name = serializers.CharField(
        source='order.customer.full_name', 
        read_only=True
    )
    amount = serializers.DecimalField(
        source='order.grand_total',
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    triggered_rules_display = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)
    
    class Meta:
        model = PaymentRisk
        fields = [
            'id',
            'order_id',
            'order_number',
            'customer_name',
            'amount',
            'risk_score',
            'risk_level',
            'flagged',
            'ip_address',
            'triggered_rules',
            'triggered_rules_display',
            'is_new_customer',
            'unusual_amount',
            'velocity_count_5min',
            'velocity_count_1hour',
            'refund_rate_percent',
            'previous_failed_attempts',
            'reviewed',
            'reviewed_by',
            'reviewed_at',
            'review_decision',
            'review_notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'risk_score',
            'triggered_rules',
            'created_at',
            'updated_at',
        ]
    
    def get_triggered_rules_display(self, obj):
        """Format triggered rules as readable names."""
        rule_names = {
            'new_customer': 'New Customer',
            'ip_velocity_5m': 'High IP Velocity (5 min)',
            'ip_velocity_1h': 'High IP Velocity (1 hour)',
            'unusual_amount': 'Unusual Amount',
            'failed_attempts': 'Previous Failed Attempts',
            'high_refund_rate': 'High Refund Rate',
        }
        return [
            rule_names.get(rule, rule) 
            for rule in (obj.triggered_rules or [])
        ]


class PaymentRiskApprovalSerializer(serializers.ModelSerializer):
    """Serializer for approving/rejecting risky payments."""
    
    class Meta:
        model = PaymentRisk
        fields = ['review_decision', 'review_notes']
    
    def validate_review_decision(self, value):
        """Validate decision is approved or rejected."""
        if value not in ['approved', 'rejected']:
            raise serializers.ValidationError(
                "Review decision must be 'approved' or 'rejected'."
            )
        return value
    
    def update(self, instance, validated_data):
        """Update risk with review information."""
        instance.reviewed = True
        instance.reviewed_by = self.context.get('request').user
        instance.reviewed_at = timezone.now()
        instance.review_decision = validated_data.get(
            'review_decision',
            instance.review_decision,
        )
        instance.review_notes = validated_data.get(
            'review_notes',
            instance.review_notes or '',
        )
        instance.save()
        return instance


class WebhookEventSerializer(serializers.ModelSerializer):
    """Serializer for webhook event details."""
    
    provider_display = serializers.CharField(
        source='get_provider_display',
        read_only=True,
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True,
    )
    
    class Meta:
        model = WebhookEvent
        fields = [
            'id',
            'provider',
            'provider_display',
            'event_id',
            'idempotency_key',
            'payload_hash',
            'status',
            'status_display',
            'signature_verified',
            'timestamp_valid',
            'idempotency_checked',
            'retry_count',
            'last_error',
            'webhook_timestamp',
            'next_retry_after',
            'created_at',
            'processed_at',
        ]
        read_only_fields = fields


class PaymentAttemptTimelineSerializer(serializers.ModelSerializer):
    """Serializer for payment attempt timeline (merchant-facing)."""
    
    provider_display = serializers.CharField(
        source='get_provider_display',
        read_only=True,
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True,
    )
    webhook_verified_display = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentAttempt
        fields = [
            'id',
            'provider',
            'provider_display',
            'status',
            'status_display',
            'provider_reference',
            'idempotency_key',
            'amount',
            'currency',
            'webhook_received',
            'webhook_verified',
            'webhook_verified_display',
            'retry_count',
            'next_retry_after',
            'created_at',
            'confirmed_at',
        ]
        read_only_fields = fields
    
    def get_webhook_verified_display(self, obj):
        """Return merchant-friendly webhook status."""
        if obj.webhook_verified:
            return "Verified & Confirmed"
        elif obj.webhook_received:
            return "Received, pending verification"
        else:
            return "Awaiting confirmation"


class PaymentAttemptDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for admin payment attempt view."""
    
    provider_display = serializers.CharField(
        source='get_provider_display',
        read_only=True,
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True,
    )
    webhook_event_details = serializers.SerializerMethodField()
    risk_details = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentAttempt
        fields = [
            'id',
            'order_id',
            'provider',
            'provider_display',
            'provider_reference',
            'status',
            'status_display',
            'amount',
            'currency',
            'idempotency_key',
            'ip_address',
            'user_agent',
            'webhook_received',
            'webhook_verified',
            'webhook_event_details',
            'retry_count',
            'last_retry_at',
            'next_retry_after',
            'retry_pending',
            'risk_details',
            'raw_response',
            'created_at',
            'confirmed_at',
        ]
        read_only_fields = fields
    
    def get_webhook_event_details(self, obj):
        """Include webhook event details if available."""
        if obj.webhook_event:
            return WebhookEventSerializer(obj.webhook_event).data
        return None
    
    def get_risk_details(self, obj):
        """Include associated risk details if available."""
        try:
            risk = PaymentRisk.objects.get(payment_attempt=obj)
            return PaymentRiskSerializer(risk).data
        except PaymentRisk.DoesNotExist:
            return None


class PaymentTimelineEventSerializer(serializers.Serializer):
    """Serializer for payment timeline event (composite view)."""
    
    timestamp = serializers.DateTimeField()
    event_type = serializers.CharField()
    status = serializers.CharField()
    message = serializers.CharField()
    metadata = serializers.JSONField(required=False)


class OrderPaymentStatusSerializer(serializers.ModelSerializer):
    """Serializer for order payment status (merchant-facing)."""
    
    payment_attempts = serializers.SerializerMethodField()
    payment_timeline = serializers.SerializerMethodField()
    overall_status = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'grand_total',
            'currency',
            'overall_status',
            'payment_attempts',
            'payment_timeline',
        ]
        read_only_fields = fields
    
    def get_payment_attempts(self, obj):
        """Get payment attempts for order."""
        attempts = PaymentAttempt.objects.filter(
            order=obj
        ).order_by('-created_at')
        return PaymentAttemptTimelineSerializer(attempts, many=True).data
    
    def get_payment_timeline(self, obj):
        """Build timeline of payment events."""
        timeline = []
        
        # Get attempts
        attempts = PaymentAttempt.objects.filter(order=obj).order_by('created_at')
        for attempt in attempts:
            timeline.append({
                'timestamp': attempt.created_at,
                'event_type': 'payment_attempt',
                'status': attempt.status,
                'message': f"Payment attempt with {attempt.get_provider_display()}",
                'metadata': {
                    'provider_reference': attempt.provider_reference,
                    'amount': str(attempt.amount),
                    'currency': attempt.currency,
                },
            })
            
            if attempt.webhook_received:
                timeline.append({
                    'timestamp': attempt.confirmed_at or timezone.now(),
                    'event_type': 'webhook_received',
                    'status': 'confirmed' if attempt.webhook_verified else 'pending',
                    'message': 'Confirmation received from payment provider',
                    'metadata': {
                        'signature_verified': attempt.webhook_verified,
                    },
                })
        
        # Get webhook events
        webhook_events = WebhookEvent.objects.filter(
            status='processed'
        ).select_related('payment_attempt__order').filter(
            payment_attempt__order=obj
        ).order_by('created_at')
        
        for event in webhook_events:
            timeline.append({
                'timestamp': event.created_at,
                'event_type': 'webhook_processed',
                'status': event.status,
                'message': f"Webhook processed: {event.event_id}",
                'metadata': {
                    'provider': event.provider,
                    'signature_verified': event.signature_verified,
                },
            })
        
        return sorted(timeline, key=lambda x: x['timestamp'])
    
    def get_overall_status(self, obj):
        """Determine overall payment status."""
        latest_attempt = PaymentAttempt.objects.filter(
            order=obj
        ).order_by('-created_at').first()
        
        if not latest_attempt:
            return 'no_payment_attempt'
        
        if latest_attempt.status == 'paid':
            return 'paid'
        elif latest_attempt.status == 'pending':
            return 'pending'
        elif latest_attempt.status in ['failed', 'cancelled']:
            return 'failed'
        else:
            return 'unknown'


class PaymentProviderSettingsSerializer(serializers.ModelSerializer):
    """Serializer for payment provider settings (admin only)."""
    
    webhook_secret_masked = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentProviderSettings
        fields = [
            'id',
            'provider_code',
            'is_active',
            'webhook_secret_masked',
            'webhook_timeout_seconds',
            'retry_max_attempts',
            'idempotency_key_required',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
        ]
    
    def get_webhook_secret_masked(self, obj):
        """Return masked webhook secret for display."""
        if not obj.webhook_secret:
            return "Not configured"
        
        secret = obj.webhook_secret
        if len(secret) > 8:
            return f"{secret[:4]}...{secret[-4:]}"
        return "****"

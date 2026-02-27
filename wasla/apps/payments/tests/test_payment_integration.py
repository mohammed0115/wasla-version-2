"""Integration tests for hardened payment system"""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from django.test import TestCase
from django.utils import timezone

from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem
from apps.payments.application.use_cases.initiate_payment import (
    InitiatePaymentCommand,
    InitiatePaymentUseCase,
)
from apps.payments.application.use_cases.handle_webhook_event import (
    HandleWebhookEventCommand,
    HandleWebhookEventUseCase,
)
from apps.payments.models import PaymentIntent, ProviderCommunicationLog
from apps.payments.security import FraudDetectionService
from apps.tenants.models import Tenant
from apps.tenants.models import StorePaymentSettings
from apps.tenants.domain.tenant_context import TenantContext
from apps.webhooks.models import WebhookEvent


class TestPaymentSystemIntegration(TestCase):
    """Integration tests for end-to-end payment flows with security features"""

    def setUp(self):
        """Set up test data"""
        self.tenant_ctx = TenantContext(
            tenant_id=12345,
            store_id=67890,
            currency="USD",
            user_id=None,
            session_key="test_session",
        )
        Tenant.objects.create(id=self.tenant_ctx.tenant_id, slug="tenant-12345", name="Tenant 12345")
        Tenant.objects.create(id=self.tenant_ctx.store_id, slug="tenant-67890", name="Tenant 67890")
        StorePaymentSettings.objects.create(
            tenant_id=self.tenant_ctx.tenant_id,
            mode=StorePaymentSettings.MODE_DUMMY,
            is_enabled=True,
        )
        from apps.payments.models import PaymentProviderSettings
        PaymentProviderSettings.objects.create(
            tenant_id=self.tenant_ctx.tenant_id,
            provider_code="dummy",
            is_enabled=True,
            is_active=True,
            webhook_secret="test_secret",
            credentials={},
        )
        self.customer = Customer.objects.create(
            store_id=self.tenant_ctx.store_id,
            email="integration@example.com",
            full_name="Integration Customer",
        )
        
        # Create test order
        self.order = Order.objects.create(
            store_id=self.tenant_ctx.store_id,
            tenant_id=self.tenant_ctx.tenant_id,
            order_number="ORD-1000",
            customer=self.customer,
            total_amount=Decimal("150.00"),
            currency="USD",
            payment_status="pending",
            status="pending",
        )

    def test_initiate_payment_with_fraud_detection(self):
        """Test payment initiation includes fraud detection"""
        cmd = InitiatePaymentCommand(
            tenant_ctx=self.tenant_ctx,
            order_id=self.order.id,
            provider_code="dummy",
            return_url="https://example.com/return",
            idempotency_key="dummy:1000:init-1",
        )
        
        with patch("apps.payments.application.facade.PaymentGatewayFacade.get") as mock_get_gateway:
            mock_gateway = Mock()
            mock_gateway.code = "dummy"
            mock_gateway.initiate_payment.return_value = Mock(
                redirect_url="https://payment.example.com",
                provider_reference="ref_123",
                client_secret=None,
            )
            mock_get_gateway.return_value = mock_gateway
            
            with patch("apps.payments.application.use_cases.payment_outcomes.OrderService.mark_as_paid"):
                result = InitiatePaymentUseCase.execute(cmd)
        
        # Payment intent should be created with fraud fields
        intent = PaymentIntent.objects.filter(order=self.order).first()
        self.assertIsNotNone(intent)
        self.assertIsNotNone(intent.risk_score)
        self.assertIsInstance(intent.risk_score, int)
        self.assertGreaterEqual(intent.risk_score, 0)
        self.assertFalse(intent.is_flagged)  # Clean payment should not be flagged
        self.assertIsInstance(intent.fraud_checks, dict)
        self.assertEqual(intent.attempt_count, 1)
        
        # Communication should be logged
        logs = ProviderCommunicationLog.objects.filter(
            tenant_id=self.tenant_ctx.tenant_id,
            provider_code="dummy",
        )
        self.assertGreater(logs.count(), 0)
        
    def test_initiate_payment_blocks_high_risk(self):
        """Test that high-risk payments are blocked"""
        # Create multiple recent payment attempts to trigger high risk
        for i in range(6):
            PaymentIntent.objects.create(
                tenant_id=self.tenant_ctx.tenant_id,
                store_id=self.tenant_ctx.store_id,
                order=self.order,
                provider_code="dummy",
                idempotency_key=f"dummy:1000:attempt_{i}",
                amount=Decimal("150.00"),
                currency="USD",
                status="failed",
                created_at=timezone.now(),
            )
        
        cmd = InitiatePaymentCommand(
            tenant_ctx=self.tenant_ctx,
            order_id=self.order.id,
            provider_code="dummy",
            return_url="https://example.com/return",
            idempotency_key="dummy:1000:init-high-risk",
        )
        
        # Should raise error due to high risk
        with self.assertRaises(ValueError) as context:
            with patch("apps.payments.application.use_cases.payment_outcomes.OrderService.mark_as_paid"):
                InitiatePaymentUseCase.execute(cmd)
        
        self.assertIn("high risk", str(context.exception).lower())
        
    def test_initiate_payment_idempotency(self):
        """Test that duplicate payment initiations are idempotent"""
        cmd = InitiatePaymentCommand(
            tenant_ctx=self.tenant_ctx,
            order_id=self.order.id,
            provider_code="dummy",
            return_url="https://example.com/return",
            idempotency_key="dummy:1000:init-idempotent",
        )
        
        with patch("apps.payments.application.facade.PaymentGatewayFacade.get") as mock_get_gateway:
            mock_gateway = Mock()
            mock_gateway.code = "dummy"
            mock_gateway.initiate_payment.return_value = Mock(
                redirect_url="https://payment.example.com",
                provider_reference="ref_123",
                client_secret=None,
            )
            mock_get_gateway.return_value = mock_gateway
            
            # Execute twice with same parameters
            with patch("apps.payments.application.use_cases.payment_outcomes.OrderService.mark_as_paid"):
                result1 = InitiatePaymentUseCase.execute(cmd)
                result2 = InitiatePaymentUseCase.execute(cmd)
        
        # Should only create one payment intent
        intents = PaymentIntent.objects.filter(order=self.order)
        self.assertEqual(intents.count(), 1)
        
        # Attempt count should be incremented
        intent = intents.first()
        self.assertEqual(intent.attempt_count, 2)
        
    def test_webhook_security_validation(self):
        """Test webhook event handling with signature validation"""
        # Create payment intent
        intent = PaymentIntent.objects.create(
            tenant_id=self.tenant_ctx.tenant_id,
            store_id=self.tenant_ctx.store_id,
            order=self.order,
            provider_code="dummy",
            idempotency_key="dummy:1000",
            provider_reference="ref_123",
            amount=Decimal("150.00"),
            currency="USD",
            status="pending",
        )
        
        cmd = HandleWebhookEventCommand(
            provider_code="dummy",
            headers={
                "X-Webhook-Signature": "test_signature",
                "X-Webhook-Timestamp": str(int(timezone.now().timestamp())),
            },
            payload={
                "event_id": "evt_123",
                "intent_reference": "ref_123",
                "status": "succeeded",
            },
            raw_body='{"event_id": "evt_123"}',
        )
        
        with patch("apps.payments.application.facade.PaymentGatewayFacade.resolve_for_webhook") as mock_resolve, \
             patch("apps.payments.application.use_cases.handle_webhook_event.WebhookSecurityValidator.verify_signature", return_value=True), \
             patch("apps.payments.application.use_cases.handle_webhook_event.WebhookSecurityValidator.check_replay_attack", return_value=True):
            mock_resolve.return_value = (
                Mock(),  # gateway
                Mock(
                    event_id="evt_123",
                    intent_reference="ref_123",
                    status="succeeded",
                ),
                self.tenant_ctx.tenant_id,
            )
            
            event = HandleWebhookEventUseCase.execute(cmd)
        
        # Webhook event should be created with security fields
        self.assertIsNotNone(event)
        self.assertEqual(event.signature, "test_signature")
        self.assertIsNotNone(event.webhook_timestamp)
        
        # Communication should be logged
        logs = ProviderCommunicationLog.objects.filter(
            operation="webhook_received"
        )
        self.assertGreater(logs.count(), 0)
        
    def test_webhook_idempotency(self):
        """Test that duplicate webhook events are idempotent"""
        # Create payment intent
        intent = PaymentIntent.objects.create(
            tenant_id=self.tenant_ctx.tenant_id,
            store_id=self.tenant_ctx.store_id,
            order=self.order,
            provider_code="dummy",
            idempotency_key="dummy:1000",
            provider_reference="ref_456",
            amount=Decimal("150.00"),
            currency="USD",
            status="pending",
        )
        
        cmd = HandleWebhookEventCommand(
            provider_code="dummy",
            headers={},
            payload={
                "event_id": "evt_456",
                "intent_reference": "ref_456",
                "status": "succeeded",
            },
            raw_body='{"event_id": "evt_456"}',
        )
        
        with patch("apps.payments.application.facade.PaymentGatewayFacade.resolve_for_webhook") as mock_resolve, \
             patch("apps.payments.application.use_cases.handle_webhook_event.WebhookSecurityValidator.verify_signature", return_value=True), \
             patch("apps.payments.application.use_cases.handle_webhook_event.WebhookSecurityValidator.check_replay_attack", return_value=True):
            mock_resolve.return_value = (
                Mock(),
                Mock(
                    event_id="evt_456",
                    intent_reference="ref_456",
                    status="succeeded",
                ),
                self.tenant_ctx.tenant_id,
            )
            
            # Process same webhook twice
            event1 = HandleWebhookEventUseCase.execute(cmd)
            event2 = HandleWebhookEventUseCase.execute(cmd)
        
        # Should return same event
        self.assertEqual(event1.id, event2.id)
        
        # Should only process once
        self.assertEqual(event1.processing_status, WebhookEvent.STATUS_PROCESSED)
        
    def test_end_to_end_payment_flow_with_security(self):
        """Test complete payment flow from initiation to webhook confirmation"""
        # Step 1: Initiate payment
        initiate_cmd = InitiatePaymentCommand(
            tenant_ctx=self.tenant_ctx,
            order_id=self.order.id,
            provider_code="dummy",
            return_url="https://example.com/return",
            idempotency_key="dummy:1000:init-e2e",
        )
        
        with patch("apps.payments.application.facade.PaymentGatewayFacade.get") as mock_get_gateway:
            mock_gateway = Mock()
            mock_gateway.code = "dummy"
            mock_gateway.initiate_payment.return_value = Mock(
                redirect_url="https://payment.example.com",
                provider_reference="ref_789",
                client_secret=None,
            )
            mock_get_gateway.return_value = mock_gateway
            
            with patch("apps.payments.application.use_cases.payment_outcomes.OrderService.mark_as_paid"):
                result = InitiatePaymentUseCase.execute(initiate_cmd)
        
        # Verify intent was created with security fields
        intent = PaymentIntent.objects.filter(order=self.order).first()
        self.assertIsNotNone(intent)
        self.assertIsNotNone(intent.risk_score)
        self.assertEqual(intent.provider_reference, "ref_789")
        
        # Step 2: Receive webhook confirmation
        webhook_cmd = HandleWebhookEventCommand(
            provider_code="dummy",
            headers={
                "X-Webhook-Signature": "hmac_signature",
                "X-Webhook-Timestamp": str(int(timezone.now().timestamp())),
            },
            payload={
                "event_id": "evt_789",
                "intent_reference": "ref_789",
                "status": "succeeded",
            },
            raw_body='{"event_id": "evt_789"}',
        )
        
        with patch("apps.payments.application.facade.PaymentGatewayFacade.resolve_for_webhook") as mock_resolve, \
             patch("apps.payments.application.use_cases.handle_webhook_event.WebhookSecurityValidator.verify_signature", return_value=True), \
             patch("apps.payments.application.use_cases.handle_webhook_event.WebhookSecurityValidator.check_replay_attack", return_value=True):
            mock_resolve.return_value = (
                Mock(),
                Mock(
                    event_id="evt_789",
                    intent_reference="ref_789",
                    status="succeeded",
                ),
                self.tenant_ctx.tenant_id,
            )
            
            event = HandleWebhookEventUseCase.execute(webhook_cmd)
        
        # Verify order was marked as paid
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "paid")
        
        # Verify webhook was processed
        self.assertEqual(event.processing_status, WebhookEvent.STATUS_PROCESSED)
        
        # Verify communication logs exist
        init_logs = ProviderCommunicationLog.objects.filter(
            operation="initiate_payment"
        )
        webhook_logs = ProviderCommunicationLog.objects.filter(
            operation="webhook_received"
        )
        self.assertGreater(init_logs.count(), 0)
        self.assertGreater(webhook_logs.count(), 0)

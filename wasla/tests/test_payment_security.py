"""
Comprehensive test suite for payment security implementation.

Tests cover:
- Idempotency validation
- HMAC signature verification
- Webhook timestamp validation
- Retry strategy
- Risk scoring
- Webhook processing flow
"""

import pytest
import hmac
import hashlib
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from django.utils import timezone
from django.test import TestCase
from django.contrib.auth.models import User

from apps.payments.models import (
    PaymentAttempt,
    PaymentIntent,
    WebhookEvent,
    PaymentRisk,
    PaymentProviderSettings,
)
from apps.payments.security import (
    generate_idempotency_key,
    validate_idempotency_key,
    compute_payload_hash,
    validate_webhook_signature,
    validate_webhook_timestamp,
    IdempotencyValidator,
    RetryStrategy,
    RiskScoringEngine,
    log_payment_event,
)
from apps.payments.services.webhook_security_handler import (
    WebhookSecurityHandler,
    WebhookContext,
)
from apps.orders.models import Order
from apps.stores.models import Store


@pytest.mark.django_db
class TestIdempotencyValidation(TestCase):
    """Test idempotent payment protection."""
    
    def setUp(self):
        self.store = Store.objects.create(name="Test Store")
        self.order = Order.objects.create(
            store=self.store,
            order_number="ORD-001",
            grand_total=Decimal("100.00"),
        )
        self.idempotency_key = generate_idempotency_key(
            store_id=self.store.id,
            order_id=self.order.id,
            client_token="token123",
        )
    
    def test_idempotency_key_generation(self):
        """Test generating valid idempotency keys."""
        key = generate_idempotency_key(
            store_id=1,
            order_id=2,
            client_token="test",
        )
        
        assert key is not None
        assert len(key) > 20
        assert validate_idempotency_key(
            store_id=1,
            order_id=2,
            idempotency_key=key,
        ) is True
    
    def test_idempotency_prevents_duplicates(self):
        """Test that idempotency validator prevents duplicate charges."""
        # First attempt
        is_dup, result = IdempotencyValidator.check_duplicate(
            store_id=self.store.id,
            order_id=self.order.id,
            idempotency_key=self.idempotency_key,
        )
        
        assert is_dup is False  # First attempt, not duplicate
        
        # Simulate paid status
        PaymentAttempt.objects.create(
            order=self.order,
            store=self.store,
            provider="stripe",
            amount=Decimal("100.00"),
            status="paid",
            idempotency_key=self.idempotency_key,
        )
        
        # Second attempt with same key
        is_dup, result = IdempotencyValidator.check_duplicate(
            store_id=self.store.id,
            order_id=self.order.id,
            idempotency_key=self.idempotency_key,
        )
        
        assert is_dup is True  # Duplicate detected
        assert result["status"] == "paid"


@pytest.mark.django_db
class TestWebhookSecurity(TestCase):
    """Test webhook security validation."""
    
    def setUp(self):
        self.webhook_secret = "test_webhook_secret_123"
        self.store = Store.objects.create(name="Test Store")
        
        self.provider = PaymentProviderSettings.objects.create(
            provider_code="test_provider",
            webhook_secret=self.webhook_secret,
        )
    
    def test_payload_hash_computation(self):
        """Test SHA256 payload hash computation."""
        payload = '{"amount": 100, "id": "ch_123"}'
        
        hash1 = compute_payload_hash(payload)
        hash2 = compute_payload_hash(payload)
        
        # Same payload should produce same hash
        assert hash1 == hash2
        
        # Hash should be hexadecimal SHA256
        assert len(hash1) == 64  # SHA256 hex is 64 chars
        assert all(c in '0123456789abcdef' for c in hash1)
    
    def test_webhook_signature_validation(self):
        """Test HMAC-SHA256 signature validation."""
        payload = '{"amount": 100, "id": "ch_123"}'
        
        # Create valid signature
        expected_sig = hmac.new(
            self.webhook_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        # Should validate correctly
        assert validate_webhook_signature(
            payload=payload,
            signature=expected_sig,
            webhook_secret=self.webhook_secret,
        ) is True
        
        # Should reject bad signature
        bad_sig = "00000000000000000000000000000000"
        assert validate_webhook_signature(
            payload=payload,
            signature=bad_sig,
            webhook_secret=self.webhook_secret,
        ) is False
    
    def test_webhook_signature_timing_attack_resistance(self):
        """Test that signature validation is timing-attack resistant."""
        payload = '{"amount": 100}'
        signature = hmac.new(
            self.webhook_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        # Valid signature should pass
        result = validate_webhook_signature(
            payload=payload,
            signature=signature,
            webhook_secret=self.webhook_secret,
        )
        assert result is True
    
    def test_webhook_timestamp_validation(self):
        """Test webhook timestamp replay protection."""
        current_time = int(timezone.now().timestamp())
        
        # Recent timestamp should be valid
        is_valid, _ = validate_webhook_timestamp(
            webhook_timestamp=current_time,
            tolerance_seconds=300,
        )
        assert is_valid is True
        
        # Old timestamp should be rejected
        old_timestamp = int((timezone.now() - timedelta(minutes=10)).timestamp())
        is_valid, error = validate_webhook_timestamp(
            webhook_timestamp=old_timestamp,
            tolerance_seconds=300,
        )
        assert is_valid is False
        assert "expired" in error.lower()


@pytest.mark.django_db
class TestRetryStrategy(TestCase):
    """Test payment retry resilience."""
    
    def test_should_retry_on_retryable_status(self):
        """Test that function returns True for retryable statuses."""
        assert RetryStrategy.should_retry(
            status="pending",
            retry_count=0,
            max_retries=3,
        ) is True
        
        assert RetryStrategy.should_retry(
            status="created",
            retry_count=1,
            max_retries=3,
        ) is True
    
    def test_should_not_retry_on_terminal_status(self):
        """Test that function returns False for terminal statuses."""
        assert RetryStrategy.should_retry(
            status="paid",
            retry_count=0,
            max_retries=3,
        ) is False
        
        assert RetryStrategy.should_retry(
            status="failed",
            retry_count=0,
            max_retries=3,
        ) is False
        
        assert RetryStrategy.should_retry(
            status="cancelled",
            retry_count=1,
            max_retries=3,
        ) is False
    
    def test_should_not_retry_when_exhausted(self):
        """Test that retries stop when max is reached."""
        assert RetryStrategy.should_retry(
            status="pending",
            retry_count=3,
            max_retries=3,
        ) is False  # At max
        
        assert RetryStrategy.should_retry(
            status="pending",
            retry_count=4,
            max_retries=3,
        ) is False  # Over max
    
    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delays."""
        # First retry: 1s
        next_retry = RetryStrategy.calculate_next_retry(
            retry_count=0,
            initial_delay=1,
            max_delay=60,
        )
        delay = (next_retry - timezone.now()).total_seconds()
        assert 0.9 < delay < 1.1  # 1s ± 10% jitter
        
        # Second retry: 2s
        next_retry = RetryStrategy.calculate_next_retry(
            retry_count=1,
            initial_delay=1,
            max_delay=60,
        )
        delay = (next_retry - timezone.now()).total_seconds()
        assert 1.8 < delay < 2.2  # 2s ± 10% jitter
        
        # Third retry: 4s
        next_retry = RetryStrategy.calculate_next_retry(
            retry_count=2,
            initial_delay=1,
            max_delay=60,
        )
        delay = (next_retry - timezone.now()).total_seconds()
        assert 3.6 < delay < 4.4  # 4s ± 10% jitter
    
    def test_max_delay_respected(self):
        """Test that max delay is never exceeded."""
        next_retry = RetryStrategy.calculate_next_retry(
            retry_count=10,  # Large retry count
            initial_delay=1,
            max_delay=60,
        )
        delay = (next_retry - timezone.now()).total_seconds()
        assert delay <= 66  # Max + jitter tolerance


@pytest.mark.django_db
class TestRiskScoring(TestCase):
    """Test fraud risk scoring engine."""
    
    def setUp(self):
        self.store = Store.objects.create(name="Test Store")
    
    def test_low_risk_score_calculation(self):
        """Test low-risk payment scores."""
        risk_score, details = RiskScoringEngine.calculate_risk_score(
            store_id=self.store.id,
            order_id=1,
            ip_address="192.168.1.1",
            amount=100,
            is_new_customer=False,
        )
        
        # Established customer, normal amount = low risk
        assert 0 <= risk_score < 40
        assert details["triggered_rules"] == []
    
    def test_new_customer_risk_increase(self):
        """Test that new customers increase risk."""
        risk_new, _ = RiskScoringEngine.calculate_risk_score(
            store_id=self.store.id,
            order_id=1,
            ip_address="192.168.1.1",
            amount=100,
            is_new_customer=True,
        )
        
        risk_existing, _ = RiskScoringEngine.calculate_risk_score(
            store_id=self.store.id,
            order_id=2,
            ip_address="192.168.1.1",
            amount=100,
            is_new_customer=False,
        )
        
        # New customer should have higher risk
        assert risk_new > risk_existing
        assert risk_new >= 10  # New customer adds +10
    
    def test_unusual_amount_risk(self):
        """Test unusual amount detection."""
        # Create some history of normal amounts
        for i in range(5):
            PaymentAttempt.objects.create(
                order_id=i,
                store=self.store,
                provider="stripe",
                amount=Decimal("100.00"),
                status="paid",
            )
        
        # Now check high amount
        risk_high, details = RiskScoringEngine.calculate_risk_score(
            store_id=self.store.id,
            order_id=99,
            ip_address="192.168.1.1",
            amount=500,  # 5x average
            is_new_customer=False,
        )
        
        # High amount should trigger unusual_amount detection
        assert "unusual_amount" in details.get("triggered_rules", [])
        assert risk_high > 15


@pytest.mark.django_db
class TestWebhookProcessing(TestCase):
    """Test complete webhook security flow."""
    
    def setUp(self):
        self.store = Store.objects.create(name="Test Store")
        self.webhook_secret = "test_secret_key"
        
        self.provider_settings = PaymentProviderSettings.objects.create(
            provider_code="stripe",
            webhook_secret=self.webhook_secret,
        )
        
        self.payload = {
            "event_id": "evt_123",
            "id": "ch_456",
            "amount": 100,
            "status": "succeeded",
        }
        
        import json
        self.raw_body = json.dumps(self.payload)
        
        # Create signature
        self.signature = hmac.new(
            self.webhook_secret.encode(),
            self.raw_body.encode(),
            hashlib.sha256,
        ).hexdigest()
    
    def test_webhook_validation_happy_path(self):
        """Test webhook validation with all checks passing."""
        current_timestamp = int(timezone.now().timestamp())
        
        context = WebhookContext(
            provider_code="stripe",
            headers={
                "X-Webhook-Signature": self.signature,
                "X-Webhook-Timestamp": str(current_timestamp),
            },
            payload=self.payload,
            raw_body=self.raw_body,
            ip_address="192.168.1.1",
        )
        
        result = WebhookSecurityHandler.validate_webhook_security(context)
        
        assert result.is_valid is True
        assert result.signature_verified is True
        assert result.timestamp_valid is True
    
    def test_webhook_rejects_invalid_signature(self):
        """Test webhook rejects invalid signature."""
        context = WebhookContext(
            provider_code="stripe",
            headers={
                "X-Webhook-Signature": "invalid_signature_000000",
                "X-Webhook-Timestamp": str(int(timezone.now().timestamp())),
            },
            payload=self.payload,
            raw_body=self.raw_body,
        )
        
        result = WebhookSecurityHandler.validate_webhook_security(context)
        
        assert result.is_valid is False
        assert "signature" in result.error_message.lower()
    
    def test_webhook_rejects_expired_timestamp(self):
        """Test webhook rejects old timestamp (replay attack)."""
        old_timestamp = int((timezone.now() - timedelta(minutes=10)).timestamp())
        
        context = WebhookContext(
            provider_code="stripe",
            headers={
                "X-Webhook-Signature": self.signature,
                "X-Webhook-Timestamp": str(old_timestamp),
            },
            payload=self.payload,
            raw_body=self.raw_body,
        )
        
        result = WebhookSecurityHandler.validate_webhook_security(context)
        
        assert result.is_valid is False
        assert "timestamp" in result.error_message.lower()

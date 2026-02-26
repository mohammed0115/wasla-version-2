"""Tests for webhook security validation"""

import time
from unittest.mock import patch

import pytest
from django.test import TestCase

from apps.payments.security.webhook_security import (
    WebhookSecurityValidator,
    IdempotencyKeyGenerator,
)


class TestWebhookSecurityValidator(TestCase):
    """Test HMAC signature validation and replay attack detection"""

    def test_compute_signature_sha256(self):
        """Test HMAC-SHA256 signature computation"""
        payload = '{"event": "payment.succeeded", "amount": 1000}'
        secret = "test_webhook_secret_key"
        
        signature = WebhookSecurityValidator.compute_signature(
            payload=payload,
            secret=secret,
            algorithm="sha256"
        )
        
        # Signature should be a hex string
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)  # SHA256 produces 64 hex chars
        
    def test_compute_signature_sha512(self):
        """Test HMAC-SHA512 signature computation"""
        payload = '{"event": "payment.succeeded"}'
        secret = "test_secret"
        
        signature = WebhookSecurityValidator.compute_signature(
            payload=payload,
            secret=secret,
            algorithm="sha512"
        )
        
        # SHA512 produces 128 hex chars
        self.assertEqual(len(signature), 128)
        
    def test_verify_signature_valid(self):
        """Test signature verification with valid signature"""
        payload = '{"event": "payment.succeeded", "order_id": "12345"}'
        secret = "webhook_secret_abc123"
        
        # Compute valid signature
        valid_signature = WebhookSecurityValidator.compute_signature(
            payload=payload,
            secret=secret,
            algorithm="sha256"
        )
        
        # Verify it
        is_valid = WebhookSecurityValidator.verify_signature(
            payload=payload,
            signature=valid_signature,
            secret=secret,
            algorithm="sha256"
        )
        
        self.assertTrue(is_valid)
        
    def test_verify_signature_invalid(self):
        """Test signature verification with tampered payload"""
        payload = '{"event": "payment.succeeded", "amount": 1000}'
        secret = "webhook_secret"
        
        # Compute signature for original
        signature = WebhookSecurityValidator.compute_signature(
            payload=payload,
            secret=secret,
            algorithm="sha256"
        )
        
        # Tamper with payload
        tampered_payload = '{"event": "payment.succeeded", "amount": 9999}'
        
        # Verification should fail
        is_valid = WebhookSecurityValidator.verify_signature(
            payload=tampered_payload,
            signature=signature,
            secret=secret,
            algorithm="sha256"
        )
        
        self.assertFalse(is_valid)
        
    def test_verify_signature_wrong_secret(self):
        """Test signature verification with wrong secret"""
        payload = '{"event": "payment.failed"}'
        correct_secret = "correct_secret"
        wrong_secret = "wrong_secret"
        
        signature = WebhookSecurityValidator.compute_signature(
            payload=payload,
            secret=correct_secret,
            algorithm="sha256"
        )
        
        # Should fail with wrong secret
        is_valid = WebhookSecurityValidator.verify_signature(
            payload=payload,
            signature=signature,
            secret=wrong_secret,
            algorithm="sha256"
        )
        
        self.assertFalse(is_valid)
        
    def test_check_replay_attack_fresh_timestamp(self):
        """Test replay attack detection with fresh timestamp"""
        current_time = int(time.time())
        
        # Timestamp from 1 minute ago (well within 5 min tolerance)
        fresh_timestamp = current_time - 60
        
        is_fresh = WebhookSecurityValidator.check_replay_attack(
            webhook_timestamp=fresh_timestamp,
            tolerance_seconds=300
        )
        
        self.assertTrue(is_fresh)
        
    def test_check_replay_attack_expired_timestamp(self):
        """Test replay attack detection with expired timestamp"""
        current_time = int(time.time())
        
        # Timestamp from 10 minutes ago (exceeds 5 min tolerance)
        expired_timestamp = current_time - 600
        
        is_fresh = WebhookSecurityValidator.check_replay_attack(
            webhook_timestamp=expired_timestamp,
            tolerance_seconds=300
        )
        
        self.assertFalse(is_fresh)
        
    def test_check_replay_attack_future_timestamp(self):
        """Test replay attack detection with future timestamp (clock skew)"""
        current_time = int(time.time())
        
        # Timestamp 10 minutes in the future
        future_timestamp = current_time + 600
        
        is_fresh = WebhookSecurityValidator.check_replay_attack(
            webhook_timestamp=future_timestamp,
            tolerance_seconds=300
        )
        
        self.assertFalse(is_fresh)
        
    def test_extract_timestamp_unix_format(self):
        """Test timestamp extraction from Unix epoch format"""
        unix_timestamp = "1704067200"  # 2024-01-01 00:00:00 UTC
        
        extracted = WebhookSecurityValidator.extract_timestamp_from_header(unix_timestamp)
        
        self.assertEqual(extracted, 1704067200)
        
    def test_extract_timestamp_iso8601_format(self):
        """Test timestamp extraction from ISO 8601 format"""
        iso_timestamp = "2024-01-01T00:00:00Z"
        
        extracted = WebhookSecurityValidator.extract_timestamp_from_header(iso_timestamp)
        
        self.assertEqual(extracted, 1704067200)
        
    def test_extract_timestamp_invalid_format(self):
        """Test timestamp extraction with invalid format"""
        invalid_timestamp = "not-a-timestamp"
        
        extracted = WebhookSecurityValidator.extract_timestamp_from_header(invalid_timestamp)
        
        self.assertIsNone(extracted)


class TestIdempotencyKeyGenerator(TestCase):
    """Test idempotency key generation and validation"""
    
    def test_generate_key_format(self):
        """Test idempotency key generation produces correct format"""
        key = IdempotencyKeyGenerator.generate(
            provider_code="stripe",
            tenant_id=12345,
            order_id=67890,
            operation="capture"
        )
        
        # Should be provider:tenant:order:operation:timestamp
        parts = key.split(":")
        self.assertEqual(len(parts), 5)
        self.assertEqual(parts[0], "stripe")
        self.assertEqual(parts[1], "12345")
        self.assertEqual(parts[2], "67890")
        self.assertEqual(parts[3], "capture")
        # Timestamp should be numeric
        self.assertTrue(parts[4].isdigit())
        
    def test_generate_key_unique(self):
        """Test that generated keys are unique (due to timestamp)"""
        key1 = IdempotencyKeyGenerator.generate(
            provider_code="paypal",
            tenant_id=1,
            order_id=100,
            operation="refund"
        )
        
        time.sleep(0.01)  # Small delay to ensure different timestamp
        
        key2 = IdempotencyKeyGenerator.generate(
            provider_code="paypal",
            tenant_id=1,
            order_id=100,
            operation="refund"
        )
        
        self.assertNotEqual(key1, key2)
        
    def test_validate_format_valid(self):
        """Test validation with valid key format"""
        valid_key = "stripe:12345:67890:authorize:1704067200000"
        
        is_valid = IdempotencyKeyGenerator.validate_format(valid_key)
        
        self.assertTrue(is_valid)
        
    def test_validate_format_invalid_parts(self):
        """Test validation with wrong number of parts"""
        invalid_key = "stripe:12345:67890"  # Only 3 parts
        
        is_valid = IdempotencyKeyGenerator.validate_format(invalid_key)
        
        self.assertFalse(is_valid)
        
    def test_validate_format_empty(self):
        """Test validation with empty string"""
        is_valid = IdempotencyKeyGenerator.validate_format("")
        
        self.assertFalse(is_valid)

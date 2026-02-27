"""Tests for provider communication logging"""

import time
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from django.test import TestCase

from apps.payments.security.communication_logger import ProviderCommunicationLogger
from apps.payments.models import ProviderCommunicationLog


class TestProviderCommunicationLogger(TestCase):
    """Test structured logging with PII sanitization"""

    def setUp(self):
        """Set up test data"""
        self.tenant_id = 12345
        self.provider_code = "stripe"

    def test_log_communication_creates_record(self):
        """Test that log_communication creates database record"""
        log = ProviderCommunicationLogger.log_communication(
            tenant_id=self.tenant_id,
            provider_code=self.provider_code,
            operation="initiate_payment",
            request_data={"amount": "100.00", "currency": "USD"},
            response_data={"status": "success", "transaction_id": "txn_123"},
            idempotency_key="test_key_001",
            status_code=200,
            duration_ms=150,
            attempt_number=1,
        )
        
        self.assertIsInstance(log, ProviderCommunicationLog)
        self.assertEqual(log.tenant_id, self.tenant_id)
        self.assertEqual(log.provider_code, self.provider_code)
        self.assertEqual(log.operation, "initiate_payment")
        self.assertEqual(log.status_code, 200)
        self.assertEqual(log.duration_ms, 150)
        
    def test_sanitize_api_key(self):
        """Test that API keys are sanitized from logs"""
        request_data = {
            "api_key": "sk_live_secret123456",
            "amount": "100.00",
        }
        
        log = ProviderCommunicationLogger.log_communication(
            tenant_id=self.tenant_id,
            provider_code=self.provider_code,
            operation="test_operation",
            request_data=request_data,
            response_data={},
            idempotency_key="test_key_002",
            status_code=200,
            attempt_number=1,
        )
        
        # API key should be redacted
        self.assertIn("api_key", log.request_data)
        self.assertEqual(log.request_data["api_key"], "[REDACTED]")
        # Amount should remain
        self.assertEqual(log.request_data["amount"], "100.00")
        
    def test_sanitize_card_number(self):
        """Test that card numbers are sanitized from logs"""
        request_data = {
            "card_number": "4111111111111111",
            "cvv": "123",
            "expiry": "12/25",
        }
        
        log = ProviderCommunicationLogger.log_communication(
            tenant_id=self.tenant_id,
            provider_code=self.provider_code,
            operation="tokenize_card",
            request_data=request_data,
            response_data={},
            idempotency_key="test_key_003",
            status_code=200,
            attempt_number=1,
        )
        
        # Sensitive fields should be redacted
        self.assertEqual(log.request_data["card_number"], "[REDACTED]")
        self.assertEqual(log.request_data["cvv"], "[REDACTED]")
        # Non-sensitive field should remain
        self.assertEqual(log.request_data["expiry"], "12/25")
        
    def test_sanitize_nested_data(self):
        """Test sanitization of nested data structures"""
        request_data = {
            "order": {
                "id": "order_123",
                "payment": {
                    "token": "tok_secret_abc",
                    "amount": "250.00",
                },
            },
        }
        
        log = ProviderCommunicationLogger.log_communication(
            tenant_id=self.tenant_id,
            provider_code=self.provider_code,
            operation="process_payment",
            request_data=request_data,
            response_data={},
            idempotency_key="test_key_004",
            status_code=200,
            attempt_number=1,
        )
        
        # Nested token should be redacted
        self.assertEqual(log.request_data["order"]["payment"]["token"], "[REDACTED]")
        # Other fields should remain
        self.assertEqual(log.request_data["order"]["id"], "order_123")
        self.assertEqual(log.request_data["order"]["payment"]["amount"], "250.00")
        
    def test_sanitize_password_and_secret(self):
        """Test that passwords and secrets are sanitized"""
        request_data = {
            "username": "test_user",
            "password": "super_secret_password",
            "secret_key": "sk_live_xyz",
            "api_secret": "secret_api_key",
        }
        
        log = ProviderCommunicationLogger.log_communication(
            tenant_id=self.tenant_id,
            provider_code=self.provider_code,
            operation="authenticate",
            request_data=request_data,
            response_data={},
            idempotency_key="test_key_005",
            status_code=200,
            attempt_number=1,
        )
        
        # All sensitive fields should be redacted
        self.assertEqual(log.request_data["password"], "[REDACTED]")
        self.assertEqual(log.request_data["secret_key"], "[REDACTED]")
        self.assertEqual(log.request_data["api_secret"], "[REDACTED]")
        # Username should remain
        self.assertEqual(log.request_data["username"], "test_user")
        
    def test_error_message_stored(self):
        """Test that error messages are stored"""
        error_msg = "Payment gateway connection timeout"
        
        log = ProviderCommunicationLogger.log_communication(
            tenant_id=self.tenant_id,
            provider_code=self.provider_code,
            operation="charge_card",
            request_data={"amount": "100.00"},
            response_data={},
            idempotency_key="test_key_006",
            status_code=500,
            error_message=error_msg,
            attempt_number=1,
        )
        
        self.assertEqual(log.error_message, error_msg)
        self.assertEqual(log.status_code, 500)
        
    def test_track_operation_context_manager_success(self):
        """Test track_operation context manager with successful operation"""
        with ProviderCommunicationLogger.track_operation(
            tenant_id=self.tenant_id,
            provider_code=self.provider_code,
            operation="refund_payment",
            request_data={"refund_amount": "50.00"},
            idempotency_key="test_key_007",
            attempt_number=1,
        ) as tracker:
            # Simulate some work
            time.sleep(0.01)
            tracker.set_response({"status": "refunded"}, status_code=200)
        
        # Should have created a log record
        log = ProviderCommunicationLog.objects.filter(
            idempotency_key="test_key_007"
        ).first()
        
        self.assertIsNotNone(log)
        self.assertEqual(log.status_code, 200)
        self.assertGreater(log.duration_ms, 0)
        self.assertIsNone(log.error_message)
        
    def test_track_operation_context_manager_error(self):
        """Test track_operation context manager with exception"""
        try:
            with ProviderCommunicationLogger.track_operation(
                tenant_id=self.tenant_id,
                provider_code=self.provider_code,
                operation="capture_payment",
                request_data={"transaction_id": "txn_999"},
                idempotency_key="test_key_008",
                attempt_number=1,
            ) as tracker:
                # Simulate an error
                raise ValueError("Payment capture failed")
        except ValueError:
            pass  # Expected
        
        # Should still have created a log record with error
        log = ProviderCommunicationLog.objects.filter(
            idempotency_key="test_key_008"
        ).first()
        
        self.assertIsNotNone(log)
        self.assertEqual(log.status_code, 500)
        self.assertIsNotNone(log.error_message)
        self.assertIn("Payment capture failed", log.error_message)
        
    def test_track_operation_measures_duration(self):
        """Test that track_operation accurately measures duration"""
        with ProviderCommunicationLogger.track_operation(
            tenant_id=self.tenant_id,
            provider_code=self.provider_code,
            operation="verify_payment",
            request_data={"payment_id": "pay_123"},
            idempotency_key="test_key_009",
            attempt_number=1,
        ) as tracker:
            # Simulate work taking ~50ms
            time.sleep(0.05)
            tracker.set_response({"verified": True}, status_code=200)
        
        log = ProviderCommunicationLog.objects.filter(
            idempotency_key="test_key_009"
        ).first()
        
        # Duration should be approximately 50ms (with some tolerance)
        self.assertGreater(log.duration_ms, 40)
        self.assertLess(log.duration_ms, 100)
        
    def test_sanitize_array_of_objects(self):
        """Test sanitization of arrays containing objects"""
        request_data = {
            "items": [
                {"name": "Product A", "price": "10.00"},
                {"name": "Product B", "price": "20.00", "secret": "hidden"},
            ],
        }
        
        log = ProviderCommunicationLogger.log_communication(
            tenant_id=self.tenant_id,
            provider_code=self.provider_code,
            operation="create_order",
            request_data=request_data,
            response_data={},
            idempotency_key="test_key_010",
            status_code=201,
            attempt_number=1,
        )
        
        # Secret in array should be redacted
        self.assertEqual(log.request_data["items"][1]["secret"], "[REDACTED]")
        # Other fields should remain
        self.assertEqual(log.request_data["items"][0]["name"], "Product A")
        self.assertEqual(log.request_data["items"][1]["price"], "20.00")
        
    def test_handle_non_serializable_data(self):
        """Test handling of non-JSON-serializable data"""
        request_data = {
            "amount": Decimal("100.50"),
            "timestamp": time.time(),
        }
        
        log = ProviderCommunicationLogger.log_communication(
            tenant_id=self.tenant_id,
            provider_code=self.provider_code,
            operation="test_operation",
            request_data=request_data,
            response_data={},
            idempotency_key="test_key_011",
            status_code=200,
            attempt_number=1,
        )
        
        # Should not crash, data should be stored (converted to string representation)
        self.assertIsNotNone(log)
        self.assertEqual(log.status_code, 200)
        
    def test_idempotency_key_uniqueness(self):
        """Test that duplicate idempotency keys are handled"""
        idempotency_key = "unique_key_001"
        
        # Create first log
        log1 = ProviderCommunicationLogger.log_communication(
            tenant_id=self.tenant_id,
            provider_code=self.provider_code,
            operation="test_operation",
            request_data={"attempt": 1},
            response_data={},
            idempotency_key=idempotency_key,
            status_code=200,
            attempt_number=1,
        )
        
        # Create second log with different data but same key
        log2 = ProviderCommunicationLogger.log_communication(
            tenant_id=self.tenant_id,
            provider_code=self.provider_code,
            operation="test_operation",
            request_data={"attempt": 2},
            response_data={},
            idempotency_key=idempotency_key,
            status_code=200,
            attempt_number=2,
        )
        
        # Both should be created (different records)
        self.assertNotEqual(log1.id, log2.id)
        
        # Should have 2 logs with this idempotency key
        logs = ProviderCommunicationLog.objects.filter(
            idempotency_key=idempotency_key
        )
        self.assertEqual(logs.count(), 2)

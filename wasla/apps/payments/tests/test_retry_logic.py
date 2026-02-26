"""Tests for payment provider retry logic"""

import time
from unittest.mock import Mock, patch

import pytest
from django.test import TestCase

from apps.payments.security.retry_logic import (
    RetryConfig,
    PaymentProviderRetry,
    RetryableError,
)


class TestRetryLogic(TestCase):
    """Test exponential backoff retry mechanism"""

    def test_execute_with_retry_success_first_attempt(self):
        """Test successful execution on first attempt (no retry needed)"""
        mock_operation = Mock(return_value="success")
        
        result = PaymentProviderRetry.execute_with_retry(
            operation=mock_operation,
            operation_name="test_operation"
        )
        
        self.assertEqual(result, "success")
        self.assertEqual(mock_operation.call_count, 1)
        
    def test_execute_with_retry_success_after_failures(self):
        """Test successful execution after initial failures"""
        mock_operation = Mock(side_effect=[
            Exception("Timeout"),
            Exception("Network error"),
            "success"
        ])
        
        result = PaymentProviderRetry.execute_with_retry(
            operation=mock_operation,
            operation_name="test_operation"
        )
        
        self.assertEqual(result, "success")
        self.assertEqual(mock_operation.call_count, 3)
        
    def test_execute_with_retry_max_attempts_exceeded(self):
        """Test failure after exhausting all retry attempts"""
        mock_operation = Mock(side_effect=Exception("Persistent failure"))
        
        with self.assertRaises(Exception) as context:
            PaymentProviderRetry.execute_with_retry(
                operation=mock_operation,
                operation_name="test_operation",
                config=RetryConfig(max_attempts=3)
            )
        
        self.assertIn("Persistent failure", str(context.exception))
        self.assertEqual(mock_operation.call_count, 3)
        
    def test_execute_with_retry_custom_config(self):
        """Test retry with custom configuration"""
        config = RetryConfig(
            max_attempts=5,
            initial_delay_ms=50,
            max_delay_ms=1000,
            exponential_base=2.0,
            jitter=True
        )
        
        mock_operation = Mock(side_effect=[
            Exception("Error 1"),
            Exception("Error 2"),
            "success"
        ])
        
        result = PaymentProviderRetry.execute_with_retry(
            operation=mock_operation,
            operation_name="test_operation",
            config=config
        )
        
        self.assertEqual(result, "success")
        self.assertEqual(mock_operation.call_count, 3)
        
    def test_execute_with_retry_non_retryable_error(self):
        """Test that non-retryable errors fail immediately"""
        # 400 Bad Request should not retry
        error_400 = Exception("HTTP 400 Bad Request")
        mock_operation = Mock(side_effect=error_400)
        
        def should_not_retry(exc):
            return "400" not in str(exc)
        
        with self.assertRaises(Exception) as context:
            PaymentProviderRetry.execute_with_retry(
                operation=mock_operation,
                operation_name="test_operation",
                config=RetryConfig(max_attempts=3),
                should_retry=should_not_retry
            )
        
        self.assertIn("400", str(context.exception))
        # Should only try once (no retries)
        self.assertEqual(mock_operation.call_count, 1)
        
    def test_retry_with_timeout_error(self):
        """Test retry behavior with timeout errors (should retry)"""
        mock_operation = Mock(side_effect=[
            Exception("Request timeout"),
            Exception("Connection timeout"),
            "success"
        ])
        
        result = PaymentProviderRetry.execute_with_retry(
            operation=mock_operation,
            operation_name="test_operation"
        )
        
        self.assertEqual(result, "success")
        self.assertEqual(mock_operation.call_count, 3)
        
    def test_retry_with_429_rate_limit(self):
        """Test retry behavior with 429 rate limit (should retry)"""
        mock_operation = Mock(side_effect=[
            Exception("HTTP 429 Too Many Requests"),
            "success"
        ])
        
        result = PaymentProviderRetry.execute_with_retry(
            operation=mock_operation,
            operation_name="test_operation"
        )
        
        self.assertEqual(result, "success")
        self.assertEqual(mock_operation.call_count, 2)
        
    def test_retry_with_502_503_504(self):
        """Test retry behavior with 502/503/504 errors (should retry)"""
        mock_operation = Mock(side_effect=[
            Exception("HTTP 502 Bad Gateway"),
            Exception("HTTP 503 Service Unavailable"),
            Exception("HTTP 504 Gateway Timeout"),
            "success"
        ])
        
        result = PaymentProviderRetry.execute_with_retry(
            operation=mock_operation,
            operation_name="test_operation",
            config=RetryConfig(max_attempts=5)
        )
        
        self.assertEqual(result, "success")
        self.assertEqual(mock_operation.call_count, 4)
        
    def test_retry_with_401_403_404(self):
        """Test no retry with authentication/not found errors"""
        mock_operation = Mock(side_effect=Exception("HTTP 401 Unauthorized"))
        
        def default_should_retry(exc):
            exc_str = str(exc).lower()
            # Don't retry on auth errors
            if any(code in exc_str for code in ["401", "403", "404"]):
                return False
            return True
        
        with self.assertRaises(Exception):
            PaymentProviderRetry.execute_with_retry(
                operation=mock_operation,
                operation_name="test_operation",
                should_retry=default_should_retry
            )
        
        # Should not retry
        self.assertEqual(mock_operation.call_count, 1)
        
    def test_before_retry_callback(self):
        """Test before_retry callback is invoked"""
        callback_invocations = []
        
        def before_retry_callback(attempt, exception):
            callback_invocations.append((attempt, str(exception)))
        
        mock_operation = Mock(side_effect=[
            Exception("Error 1"),
            Exception("Error 2"),
            "success"
        ])
        
        result = PaymentProviderRetry.execute_with_retry(
            operation=mock_operation,
            operation_name="test_operation",
            before_retry=before_retry_callback
        )
        
        # Should have 2 callback invocations (before retry 2 and 3)
        self.assertEqual(len(callback_invocations), 2)
        self.assertEqual(callback_invocations[0][0], 2)
        self.assertIn("Error 1", callback_invocations[0][1])
        
    def test_on_final_failure_callback(self):
        """Test on_final_failure callback is invoked after exhausting retries"""
        final_failure_data = {}
        
        def on_final_failure_callback(attempts, exception):
            final_failure_data["attempts"] = attempts
            final_failure_data["exception"] = str(exception)
        
        mock_operation = Mock(side_effect=Exception("Persistent error"))
        
        with self.assertRaises(Exception):
            PaymentProviderRetry.execute_with_retry(
                operation=mock_operation,
                operation_name="test_operation",
                config=RetryConfig(max_attempts=3),
                on_final_failure=on_final_failure_callback
            )
        
        self.assertEqual(final_failure_data["attempts"], 3)
        self.assertIn("Persistent error", final_failure_data["exception"])
        
    def test_exponential_backoff_delays(self):
        """Test that delays increase exponentially"""
        delays = []
        
        def mock_sleep(seconds):
            delays.append(seconds)
        
        mock_operation = Mock(side_effect=[
            Exception("Error 1"),
            Exception("Error 2"),
            Exception("Error 3"),
            "success"
        ])
        
        config = RetryConfig(
            max_attempts=4,
            initial_delay_ms=100,
            exponential_base=2.0,
            jitter=False  # Disable jitter for predictable testing
        )
        
        with patch("time.sleep", mock_sleep):
            result = PaymentProviderRetry.execute_with_retry(
                operation=mock_operation,
                operation_name="test_operation",
                config=config
            )
        
        # Should have 3 delays: 100ms, 200ms, 400ms
        self.assertEqual(len(delays), 3)
        self.assertAlmostEqual(delays[0], 0.1, places=2)
        self.assertAlmostEqual(delays[1], 0.2, places=2)
        self.assertAlmostEqual(delays[2], 0.4, places=2)
        
    def test_jitter_adds_randomness(self):
        """Test that jitter adds randomness to delays"""
        delays = []
        
        def mock_sleep(seconds):
            delays.append(seconds)
        
        mock_operation = Mock(side_effect=[
            Exception("Error 1"),
            Exception("Error 2"),
            "success"
        ])
        
        config = RetryConfig(
            max_attempts=3,
            initial_delay_ms=100,
            exponential_base=2.0,
            jitter=True  # Enable jitter
        )
        
        with patch("time.sleep", mock_sleep):
            result = PaymentProviderRetry.execute_with_retry(
                operation=mock_operation,
                operation_name="test_operation",
                config=config
            )
        
        # Delays should be different due to jitter
        # But should be within reasonable bounds (50%-150% of base delay)
        self.assertEqual(len(delays), 2)
        self.assertGreater(delays[0], 0.05)  # At least 50ms
        self.assertLess(delays[0], 0.15)     # At most 150ms
        
    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay_ms"""
        delays = []
        
        def mock_sleep(seconds):
            delays.append(seconds)
        
        mock_operation = Mock(side_effect=[
            Exception("Error") for _ in range(10)
        ] + ["success"])
        
        config = RetryConfig(
            max_attempts=11,
            initial_delay_ms=100,
            max_delay_ms=500,  # Cap at 500ms
            exponential_base=2.0,
            jitter=False
        )
        
        with patch("time.sleep", mock_sleep):
            result = PaymentProviderRetry.execute_with_retry(
                operation=mock_operation,
                operation_name="test_operation",
                config=config
            )
        
        # Later delays should be capped at 500ms
        self.assertTrue(all(delay <= 0.5 for delay in delays[-5:]))
        
    def test_retryable_error_exception(self):
        """Test custom RetryableError exception"""
        error = RetryableError("Custom retryable error")
        
        self.assertIsInstance(error, Exception)
        self.assertEqual(str(error), "Custom retryable error")

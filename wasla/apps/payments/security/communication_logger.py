"""Structured logging service for payment provider communication."""
from __future__ import annotations

from decimal import Decimal
import time
from contextlib import contextmanager
from typing import Any

from django.utils import timezone

from apps.payments.models import ProviderCommunicationLog


class ProviderCommunicationLogger:
    """Service for logging all payment provider API communication."""

    @staticmethod
    def log_communication(
        *,
        tenant_id: int | None,
        provider_code: str,
        operation: str,
        request_data: dict,
        response_data: dict | None = None,
        status_code: int | None = None,
        error_message: str | None = None,
        duration_ms: int | None = None,
        attempt_number: int = 1,
        idempotency_key: str,
    ) -> ProviderCommunicationLog:
        """
        Log a provider API communication event.
        
        Args:
            tenant_id: Tenant identifier
            provider_code: Payment provider code (tap, stripe, etc.)
            operation: Operation type (initiate_payment, verify_callback, refund)
            request_data: Sanitized request payload
            response_data: Provider response payload
            status_code: HTTP status code
            error_message: Error message if failed
            duration_ms: Request duration in milliseconds
            attempt_number: Retry attempt number
            idempotency_key: Idempotency key for correlation
            
        Returns:
            Created log entry
        """
        # Sanitize sensitive data
        sanitized_request = ProviderCommunicationLogger._sanitize_data(request_data)
        sanitized_response = ProviderCommunicationLogger._sanitize_data(response_data or {})
        
        log_entry = ProviderCommunicationLog.objects.create(
            tenant_id=tenant_id,
            provider_code=provider_code,
            operation=operation,
            request_data=sanitized_request,
            response_data=sanitized_response,
            status_code=status_code,
            error_message=error_message[:1000] if error_message else None,  # Truncate long errors
            duration_ms=duration_ms,
            attempt_number=attempt_number,
            idempotency_key=idempotency_key[:120],  # Ensure fits in field
        )
        
        return log_entry

    @staticmethod
    @contextmanager
    def track_operation(
        *,
        tenant_id: int | None,
        provider_code: str,
        operation: str,
        request_data: dict,
        idempotency_key: str,
        attempt_number: int = 1,
    ):
        """
        Context manager to track provider operation with automatic timing and logging.
        
        Usage:
            with ProviderCommunicationLogger.track_operation(...) as tracker:
                response = call_provider_api()
                tracker.set_response(response)
        """
        start_time = time.time()
        tracker = OperationTracker()
        
        try:
            yield tracker
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            ProviderCommunicationLogger.log_communication(
                tenant_id=tenant_id,
                provider_code=provider_code,
                operation=operation,
                request_data=request_data,
                response_data=tracker.response_data,
                status_code=tracker.status_code,
                error_message=None,
                duration_ms=duration_ms,
                attempt_number=attempt_number,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            
            ProviderCommunicationLogger.log_communication(
                tenant_id=tenant_id,
                provider_code=provider_code,
                operation=operation,
                request_data=request_data,
                response_data=tracker.response_data,
                status_code=tracker.status_code or 500,
                error_message=str(exc),
                duration_ms=duration_ms,
                attempt_number=attempt_number,
                idempotency_key=idempotency_key,
            )
            raise

    @staticmethod
    def _sanitize_data(data: dict) -> dict:
        """Remove or mask sensitive fields from log data."""
        if not data:
            return {}
        
        sensitive_keys = {
            "secret_key",
            "secret",
            "api_key",
            "password",
            "token",
            "authorization",
            "card_number",
            "cvv",
            "cvc",
            "pin",
        }
        
        sanitized = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            # Check if key contains sensitive pattern
            is_sensitive = any(pattern in key_lower for pattern in sensitive_keys)
            
            if is_sensitive:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = ProviderCommunicationLogger._sanitize_data(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    ProviderCommunicationLogger._sanitize_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            elif isinstance(value, Decimal):
                sanitized[key] = str(value)
            else:
                try:
                    import json
                    json.dumps(value)
                except TypeError:
                    sanitized[key] = str(value)
                    continue
                sanitized[key] = value
        
        return sanitized


class OperationTracker:
    """Helper class for tracking operation results in context manager."""
    
    def __init__(self):
        self.response_data: dict = {}
        self.status_code: int | None = None
    
    def set_response(self, data: dict, status_code: int | None = None):
        """Set response data from provider."""
        self.response_data = data
        self.status_code = status_code

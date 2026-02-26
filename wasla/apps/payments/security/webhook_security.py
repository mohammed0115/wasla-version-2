"""Payment system security utilities for webhook validation and replay protection."""
from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone as dt_timezone

from django.utils import timezone


class WebhookSecurityValidator:
    """HMAC signature validation and replay attack protection for webhooks."""

    REPLAY_WINDOW_SECONDS = 300  # 5 minutes

    @staticmethod
    def compute_signature(*, payload: str, secret: str, algorithm: str = "sha256") -> str:
        """Compute HMAC signature for webhook payload."""
        if not secret:
            raise ValueError("Webhook secret is required")
        
        payload_bytes = payload.encode("utf-8")
        secret_bytes = secret.encode("utf-8")
        
        if algorithm == "sha256":
            signature = hmac.new(secret_bytes, payload_bytes, hashlib.sha256).hexdigest()
        elif algorithm == "sha512":
            signature = hmac.new(secret_bytes, payload_bytes, hashlib.sha512).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        return signature

    @staticmethod
    def verify_signature(
        *,
        payload: str,
        signature: str,
        secret: str,
        algorithm: str = "sha256",
    ) -> bool:
        """Verify HMAC signature for webhook payload."""
        try:
            expected = WebhookSecurityValidator.compute_signature(
                payload=payload,
                secret=secret,
                algorithm=algorithm,
            )
            return hmac.compare_digest(signature, expected)
        except Exception:
            return False

    @staticmethod
    def check_replay_attack(
        webhook_timestamp: int,
        tolerance_seconds: int | None = None,
    ) -> bool:
        """
        Check if webhook timestamp is within acceptable window.
        
        Args:
            webhook_timestamp: Unix timestamp (seconds since epoch)
            tolerance_seconds: Maximum age in seconds (default 300)
        
        Returns:
            True if timestamp is fresh, False if expired/invalid
        """
        if tolerance_seconds is None:
            tolerance_seconds = WebhookSecurityValidator.REPLAY_WINDOW_SECONDS
        
        if not webhook_timestamp:
            return False
        
        current_time = int(time.time())
        time_diff = abs(current_time - webhook_timestamp)
        
        # Reject if outside tolerance window
        if time_diff > tolerance_seconds:
            return False
        
        # Reject future timestamps beyond small clock skew (60 seconds)
        if webhook_timestamp > current_time + 60:
            return False
        
        return True

    @staticmethod
    def extract_timestamp_from_header(header_value: str) -> int | None:
        """
        Extract timestamp from webhook header.
        
        Common formats:
        - Unix timestamp: "1677649200"
        - ISO 8601: "2023-03-01T12:00:00Z"
        
        Returns:
            Unix timestamp as int, or None if invalid
        """
        if not header_value:
            return None
        
        try:
            # Try unix timestamp first
            return int(header_value)
        except ValueError:
            pass
        
        try:
            # Try ISO 8601 and convert to Unix timestamp
            dt = datetime.fromisoformat(header_value.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except ValueError:
            pass
        
        return None


class IdempotencyKeyGenerator:
    """Generate and validate idempotency keys for payment operations."""

    @staticmethod
    def generate(
        *,
        tenant_id: int,
        order_id: int,
        provider_code: str,
        operation: str = "payment",
    ) -> str:
        """Generate idempotency key for payment operation."""
        return f"{provider_code}:{tenant_id}:{order_id}:{operation}:{int(time.time() * 1000)}"

    @staticmethod
    def validate_format(key: str) -> bool:
        """Basic validation of idempotency key format."""
        if not key or len(key) > 120:
            return False
        parts = key.split(":")
        if len(parts) != 5:
            return False
        provider_code, tenant_id, order_id, operation, timestamp = parts
        if not provider_code or not operation:
            return False
        if not tenant_id.isdigit() or not order_id.isdigit() or not timestamp.isdigit():
            return False
        return True

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Final
import time

DEFAULT_SIGNATURE_HEADER: Final[str] = "X-Signature"


def _normalize_signature(signature: str) -> str:
    if not signature:
        return ""
    value = signature.strip()
    if value.startswith("sha256="):
        return value.split("=", 1)[1].strip()
    if "," in value and "=" in value:
        parts = {}
        for item in value.split(","):
            if "=" not in item:
                continue
            key, val = item.split("=", 1)
            parts[key.strip()] = val.strip()
        for key in ("v1", "signature", "sig"):
            if key in parts:
                return parts[key]
    return value


def compute_hmac_signature(secret: str, payload: str, *, encoding: str = "hex") -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    if encoding == "base64":
        return base64.b64encode(digest).decode("utf-8")
    return digest.hex()


def verify_hmac_signature(signature: str, *, secret: str, payload: str, encoding: str = "hex") -> bool:
    if not secret or not payload:
        return False
    provided = _normalize_signature(signature)
    if not provided:
        return False
    expected = compute_hmac_signature(secret, payload, encoding=encoding)
    return hmac.compare_digest(provided, expected)


def extract_stripe_timestamp(signature: str) -> int | None:
    """Extract Stripe webhook timestamp from Stripe-Signature header."""
    if not signature:
        return None
    try:
        parts = {}
        for part in signature.split(","):
            if "=" not in part:
                continue
            key, val = part.split("=", 1)
            parts[key.strip()] = val.strip()
        timestamp = parts.get("t")
        if not timestamp:
            return None
        return int(timestamp)
    except (ValueError, TypeError):
        return None


def compute_stripe_signature(*, secret: str, timestamp: int, payload: str) -> str:
    """Compute Stripe v1 signature for a given payload."""
    signed_payload = f"{timestamp}.{payload}"
    digest = hmac.new(secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest


def verify_stripe_signature(
    signature: str,
    *,
    secret: str,
    payload: str,
    tolerance_seconds: int = 300,
) -> bool:
    """
    Verify Stripe webhook signature (Stripe-Signature header).

    Uses HMAC-SHA256 over "{timestamp}.{payload}" and checks replay window.
    """
    if not secret or not signature:
        return False
    timestamp = extract_stripe_timestamp(signature)
    if not timestamp:
        return False
    # Reject stale or far-future timestamps.
    now = int(time.time())
    if abs(now - timestamp) > int(tolerance_seconds or 300):
        return False
    if timestamp > now + 60:
        return False
    try:
        expected = compute_stripe_signature(secret=secret, timestamp=timestamp, payload=payload)
    except Exception:
        return False
    provided = _normalize_signature(signature)
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)

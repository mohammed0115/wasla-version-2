from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Final

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

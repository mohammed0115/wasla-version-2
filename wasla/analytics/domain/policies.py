from __future__ import annotations

import hashlib
import re
from typing import Any

from django.conf import settings


_EVENT_NAME_RE = re.compile(r"^[a-z0-9_.-]+$")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{6,}")

PII_KEYS = {
    "email",
    "phone",
    "full_name",
    "name",
    "address",
    "street",
    "city",
    "zip",
    "postal",
    "password",
}


def validate_event_name(name: str) -> str:
    value = (name or "").strip()
    if not value or not _EVENT_NAME_RE.match(value):
        raise ValueError("Invalid event name.")
    return value


def normalize_actor_type(value: str) -> str:
    upper = (value or "").strip().upper()
    return upper if upper in {"ANON", "CUSTOMER", "MERCHANT", "ADMIN"} else "ANON"


def hash_identifier(value: str | int | None) -> str:
    if value is None:
        return ""
    salt = (getattr(settings, "ANALYTICS_HASH_SALT", "") or getattr(settings, "SECRET_KEY", "")).strip()
    raw = f"{salt}:{value}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def redact_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        if _EMAIL_RE.search(value) or _PHONE_RE.search(value):
            return "[redacted]"
        return value
    if isinstance(value, dict):
        return redact_properties(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return value


def redact_properties(props: dict[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in (props or {}).items():
        key_norm = str(key).lower()
        if key_norm in PII_KEYS:
            result[key] = "[redacted]"
        else:
            result[key] = redact_value(value)
    return result

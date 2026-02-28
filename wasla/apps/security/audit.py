from __future__ import annotations

from typing import Any

from apps.security.models import SecurityAuditLog


def get_client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def log_security_event(
    *,
    request,
    event_type: str,
    outcome: str,
    metadata: dict[str, Any] | None = None,
    user=None,
) -> None:
    try:
        actor = user
        if actor is None and getattr(request, "user", None) and request.user.is_authenticated:
            actor = request.user

        SecurityAuditLog.objects.create(
            event_type=event_type,
            outcome=outcome,
            user=actor,
            path=(request.path or "")[:255],
            method=(request.method or "")[:12],
            ip_address=get_client_ip(request)[:64],
            metadata=metadata or {},
        )
    except Exception:
        return

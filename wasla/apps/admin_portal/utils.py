from __future__ import annotations

from typing import Any

from .models import AdminAuditLog


def _client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def log_admin_action(request, action: str, obj: Any, before_dict: dict | None, after_dict: dict | None) -> AdminAuditLog:
    object_type = obj.__class__.__name__
    object_id = str(getattr(obj, "pk", ""))
    return AdminAuditLog.objects.create(
        actor=request.user,
        action=action,
        object_type=object_type,
        object_id=object_id,
        before=before_dict,
        after=after_dict,
        ip_address=_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
    )

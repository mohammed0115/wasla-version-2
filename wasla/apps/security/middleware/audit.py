from __future__ import annotations

from apps.security.audit import log_security_event
from apps.security.models import SecurityAuditLog


class SecurityAuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        path = (request.path or "").lower()
        method = (request.method or "GET").upper()

        if path.startswith("/api/payments/") and method in {"POST", "PUT", "PATCH", "DELETE"}:
            outcome = (
                SecurityAuditLog.OUTCOME_SUCCESS
                if int(getattr(response, "status_code", 500)) < 400
                else SecurityAuditLog.OUTCOME_FAILURE
            )
            log_security_event(
                request=request,
                event_type=SecurityAuditLog.EVENT_PAYMENT,
                outcome=outcome,
                metadata={"status_code": int(getattr(response, "status_code", 500))},
            )

        return response

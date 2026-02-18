from __future__ import annotations

import uuid

from django.utils.deprecation import MiddlewareMixin

from apps.observability.logging import bind_request_context, clear_request_context


class RequestIdMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.request_id = request_id
        tenant_id = getattr(getattr(request, "tenant", None), "id", None)
        user_id = request.user.id if getattr(request, "user", None) and request.user.is_authenticated else None
        bind_request_context(
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
            path=request.path,
            method=request.method,
        )

    def process_response(self, request, response):
        request_id = getattr(request, "request_id", None)
        if request_id:
            response["X-Request-Id"] = request_id
        clear_request_context()
        return response

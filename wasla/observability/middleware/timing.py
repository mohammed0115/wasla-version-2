from __future__ import annotations

import logging
from time import monotonic

from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin

from observability.logging import bind_request_context
logger = logging.getLogger("wasla.request")


class TimingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request._start_time = monotonic()

    def process_exception(self, request, exception):
        latency_ms = _compute_latency_ms(request)
        _increment_metrics(status_code=500)
        logger.error(
            "request_error",
            extra={"status_code": 500, "latency_ms": latency_ms, "error_code": type(exception).__name__},
        )

    def process_response(self, request, response):
        request_id = getattr(request, "request_id", None) or ""
        tenant_id = getattr(getattr(request, "tenant", None), "id", None)
        user_id = request.user.id if getattr(request, "user", None) and request.user.is_authenticated else None
        bind_request_context(
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
            path=request.path,
            method=request.method,
        )
        latency_ms = _compute_latency_ms(request)
        response["X-Response-Time-ms"] = str(latency_ms)
        status_code = getattr(response, "status_code", 200)
        _increment_metrics(status_code=status_code)
        logger.info(
            "request_complete",
            extra={"status_code": status_code, "latency_ms": latency_ms},
        )
        return response


def _compute_latency_ms(request) -> int:
    start = getattr(request, "_start_time", None)
    if not start:
        return 0
    return int((monotonic() - start) * 1000)


def _increment_metrics(*, status_code: int):
    try:
        cache.incr("metrics:requests:total", 1)
    except Exception:
        cache.set("metrics:requests:total", 1, timeout=None)
    key = f"metrics:requests:status:{status_code}"
    try:
        cache.incr(key, 1)
    except Exception:
        cache.set(key, 1, timeout=None)

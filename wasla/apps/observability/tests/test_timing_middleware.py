from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from apps.observability.middleware.timing import TimingMiddleware
from apps.observability.models import RequestPerformanceLog
from core.infrastructure.store_cache import StoreCacheService


class _AnonymousUser:
    is_authenticated = False


@override_settings(PERFORMANCE_LOG_PERSIST_ENABLED=True)
def test_timing_middleware_sets_headers_and_persists_log(db):
    def get_response(request):
        StoreCacheService.get_or_set(
            store_id=55,
            namespace="test_ns",
            key_parts=["k"],
            producer=lambda: {"a": 1},
            timeout=30,
        )
        return HttpResponse("ok", status=200)

    middleware = TimingMiddleware(get_response)
    request = RequestFactory().get("/storefront")
    request.tenant = SimpleNamespace(id=55)
    request.user = _AnonymousUser()

    response = middleware(request)

    assert response.status_code == 200
    assert "X-Response-Time-ms" in response
    assert response["X-Cache"] in {"HIT", "MISS"}
    assert RequestPerformanceLog.objects.filter(endpoint="/storefront", store_id=55).exists()


@override_settings(PERFORMANCE_LOG_PERSIST_ENABLED=True)
def test_timing_middleware_logs_slow_request_warning(db):
    def get_response(request):
        return HttpResponse("ok", status=200)

    middleware = TimingMiddleware(get_response)
    request = RequestFactory().get("/slow-path")
    request.tenant = SimpleNamespace(id=99)
    request.user = _AnonymousUser()

    with patch("apps.observability.middleware.timing._compute_latency_ms", return_value=650):
        with patch("apps.observability.middleware.timing.performance_logger.warning") as warning_mock:
            response = middleware(request)

    assert response.status_code == 200
    warning_mock.assert_called()

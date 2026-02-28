from __future__ import annotations

import logging
from time import monotonic

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils.deprecation import MiddlewareMixin

from apps.observability.logging import bind_request_context
from apps.observability.metrics_registry import REQUEST_TOTAL, REQUEST_LATENCY_MS, SLOW_QUERY_TOTAL
from core.infrastructure.store_cache import StoreCacheService
logger = logging.getLogger("wasla.request")
performance_logger = logging.getLogger("wasla.performance")


class TimingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request._start_time = monotonic()
        request._db_query_count_start = len(getattr(connection, "queries", []))
        request._db_queries_start = list(getattr(connection, "queries", []))
        StoreCacheService.set_cache_hit(False)

    def process_exception(self, request, exception):
        latency_ms = _compute_latency_ms(request)
        query_count = _compute_query_count(request)
        cache_hit = StoreCacheService.consume_cache_hit()
        cache_status = "HIT" if cache_hit else "MISS"
        store_id = _resolve_store_id(request)
        _increment_metrics(status_code=500)
        logger.error(
            "request_error",
            extra={
                "status_code": 500,
                "latency_ms": latency_ms,
                "error_code": type(exception).__name__,
                "store_id": store_id,
                "query_count": query_count,
                "cache_status": cache_status,
            },
        )
        self._persist_metric(
            request=request,
            status_code=500,
            latency_ms=latency_ms,
            query_count=query_count,
            cache_hit=cache_hit,
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
        query_count = _compute_query_count(request)
        cache_hit = StoreCacheService.consume_cache_hit()
        cache_status = "HIT" if cache_hit else "MISS"
        store_id = _resolve_store_id(request)
        response["X-Response-Time-ms"] = str(latency_ms)
        response["X-Cache"] = "HIT" if cache_hit else "MISS"
        status_code = getattr(response, "status_code", 200)
        _increment_metrics(status_code=status_code)
        _observe_metrics(request=request, status_code=status_code, latency_ms=latency_ms)
        logger.info(
            "request_complete",
            extra={
                "status_code": status_code,
                "latency_ms": latency_ms,
                "store_id": store_id,
                "query_count": query_count,
                "cache_status": cache_status,
            },
        )
        if latency_ms > 500:
            performance_logger.warning(
                "slow_request",
                extra={
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                    "store_id": store_id,
                    "query_count": query_count,
                    "cache_status": cache_status,
                    "path": getattr(request, "path", ""),
                },
            )
        performance_logger.info(
            "request_performance",
            extra={
                "status_code": status_code,
                "latency_ms": latency_ms,
                "store_id": store_id,
                "query_count": query_count,
                "cache_status": cache_status,
            },
        )
        self._persist_metric(
            request=request,
            status_code=status_code,
            latency_ms=latency_ms,
            query_count=query_count,
            cache_hit=cache_hit,
        )
        _log_slow_queries(request)
        return response

    def _persist_metric(self, *, request, status_code: int, latency_ms: int, query_count: int, cache_hit: bool):
        if not getattr(settings, "PERFORMANCE_LOG_PERSIST_ENABLED", True):
            return
        slow_threshold = float(getattr(settings, "PERFORMANCE_SLOW_THRESHOLD_MS", 500.0))
        try:
            from apps.observability.models import RequestPerformanceLog
            from apps.observability.models import PerformanceLog

            RequestPerformanceLog.objects.create(
                request_id=getattr(request, "request_id", "") or "",
                store_id=_resolve_store_id(request),
                endpoint=(getattr(request, "path", "") or "")[:255],
                method=(getattr(request, "method", "GET") or "GET")[:10],
                status_code=int(status_code),
                response_time_ms=float(latency_ms),
                db_query_count=max(0, int(query_count)),
                cache_hit=bool(cache_hit),
                is_slow=float(latency_ms) >= slow_threshold,
            )
            PerformanceLog.objects.create(
                path=(getattr(request, "path", "") or "")[:255],
                method=(getattr(request, "method", "GET") or "GET")[:10],
                store=_resolve_store_id(request),
                duration_ms=float(latency_ms),
                query_count=max(0, int(query_count)),
                status_code=int(status_code),
                request_id=getattr(request, "request_id", "") or "",
            )
        except Exception:  # pragma: no cover
            return


class PerformanceMiddleware(TimingMiddleware):
    pass


def _compute_latency_ms(request) -> int:
    start = getattr(request, "_start_time", None)
    if not start:
        return 0
    return int((monotonic() - start) * 1000)


def _compute_query_count(request) -> int:
    start = int(getattr(request, "_db_query_count_start", 0) or 0)
    now = len(getattr(connection, "queries", []))
    if now < start:
        return 0
    return now - start


def _resolve_store_id(request) -> int:
    store = getattr(request, "store", None)
    if store is not None and getattr(store, "id", None):
        return int(store.id)
    tenant = getattr(request, "tenant", None)
    if tenant is not None and getattr(tenant, "id", None):
        return int(tenant.id)
    return 0


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


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    if path.startswith("/api/"):
        return "/api/*"
    if path.startswith("/admin-portal/"):
        return "/admin-portal/*"
    return path


def _observe_metrics(*, request, status_code: int, latency_ms: int):
    try:
        method = (getattr(request, "method", "GET") or "GET").upper()
        path = _normalize_path(getattr(request, "path", "") or "")
        REQUEST_TOTAL.labels(method=method, path=path, status=str(status_code)).inc()
        REQUEST_LATENCY_MS.labels(method=method, path=path).observe(float(latency_ms))
    except Exception:
        return


def _log_slow_queries(request):
    threshold_ms = float(getattr(settings, "PERFORMANCE_SLOW_QUERY_THRESHOLD_MS", 250.0) or 250.0)
    if threshold_ms <= 0:
        return

    all_queries = list(getattr(connection, "queries", []))
    start_count = len(getattr(request, "_db_queries_start", []) or [])
    request_queries = all_queries[start_count:]

    for item in request_queries:
        elapsed_s = float(item.get("time", 0.0) or 0.0)
        elapsed_ms = elapsed_s * 1000.0
        if elapsed_ms < threshold_ms:
            continue

        sql_text = (item.get("sql") or "").strip()
        sql_signature = " ".join(sql_text.split())[:120]
        performance_logger.warning(
            "slow_query",
            extra={
                "duration_ms": round(elapsed_ms, 2),
                "path": getattr(request, "path", ""),
                "query_count": len(request_queries),
                "error_code": "SLOW_QUERY",
                "cache_status": "N/A",
                "store_id": _resolve_store_id(request),
                "query_signature": sql_signature,
            },
        )
        try:
            SLOW_QUERY_TOTAL.labels(path=_normalize_path(getattr(request, "path", "") or "")).inc()
        except Exception:
            pass

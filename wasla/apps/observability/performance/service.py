from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from statistics import mean
from time import perf_counter

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext


@dataclass(frozen=True)
class EndpointPerformanceMetric:
    path: str
    method: str
    runs: int
    status_codes: list[int]
    average_response_ms: float
    min_response_ms: float
    max_response_ms: float
    average_query_count: float
    min_query_count: int
    max_query_count: int
    errors: list[str]


def evaluate_endpoint(
    *,
    client: Client,
    path: str,
    method: str = "GET",
    runs: int = 3,
    data: dict | None = None,
) -> EndpointPerformanceMetric:
    normalized_method = (method or "GET").upper()
    timings_ms: list[float] = []
    query_counts: list[int] = []
    status_codes: list[int] = []
    errors: list[str] = []

    for _ in range(max(1, runs)):
        started = perf_counter()
        try:
            with CaptureQueriesContext(connection) as queries_ctx:
                response = client.generic(normalized_method, path, data=data or {})
            elapsed_ms = (perf_counter() - started) * 1000.0
            timings_ms.append(round(elapsed_ms, 3))
            query_counts.append(len(queries_ctx.captured_queries))
            status_codes.append(int(getattr(response, "status_code", 0) or 0))
        except Exception as exc:  # pragma: no cover - defensive runtime path
            elapsed_ms = (perf_counter() - started) * 1000.0
            timings_ms.append(round(elapsed_ms, 3))
            query_counts.append(0)
            status_codes.append(0)
            errors.append(str(exc))

    return EndpointPerformanceMetric(
        path=path,
        method=normalized_method,
        runs=max(1, runs),
        status_codes=status_codes,
        average_response_ms=round(mean(timings_ms), 3),
        min_response_ms=round(min(timings_ms), 3),
        max_response_ms=round(max(timings_ms), 3),
        average_query_count=round(mean(query_counts), 3),
        min_query_count=min(query_counts),
        max_query_count=max(query_counts),
        errors=errors,
    )


def build_performance_report(
    *,
    endpoint_specs: list[dict],
    runs_per_endpoint: int = 3,
    slow_threshold_ms: float = 500.0,
    host: str = "localhost",
) -> dict:
    client = Client(HTTP_HOST=host)
    metrics: list[EndpointPerformanceMetric] = []

    for spec in endpoint_specs:
        path = str(spec.get("path") or "").strip()
        if not path:
            continue
        method = str(spec.get("method") or "GET")
        data = spec.get("data") if isinstance(spec.get("data"), dict) else None
        metric = evaluate_endpoint(
            client=client,
            path=path,
            method=method,
            runs=runs_per_endpoint,
            data=data,
        )
        metrics.append(metric)

    if metrics:
        all_avg_times = [item.average_response_ms for item in metrics]
        all_avg_queries = [item.average_query_count for item in metrics]
        overall_avg_ms = round(mean(all_avg_times), 3)
        overall_avg_queries = round(mean(all_avg_queries), 3)
    else:
        overall_avg_ms = 0.0
        overall_avg_queries = 0.0

    slow_endpoints = [
        asdict(item)
        for item in metrics
        if item.average_response_ms >= float(slow_threshold_ms)
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs_per_endpoint": max(1, runs_per_endpoint),
        "slow_threshold_ms": float(slow_threshold_ms),
        "summary": {
            "endpoint_count": len(metrics),
            "average_api_response_ms": overall_avg_ms,
            "average_db_query_count": overall_avg_queries,
            "slow_endpoint_count": len(slow_endpoints),
        },
        "endpoints": [asdict(item) for item in metrics],
        "slow_endpoints": slow_endpoints,
    }

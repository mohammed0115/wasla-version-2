from __future__ import annotations

from prometheus_client import Counter, Histogram

REQUEST_TOTAL = Counter(
    "wasla_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

REQUEST_LATENCY_MS = Histogram(
    "wasla_http_request_latency_ms",
    "HTTP request latency in milliseconds",
    ["method", "path"],
    buckets=(10, 25, 50, 100, 250, 500, 1000, 2500, 5000),
)

SLOW_QUERY_TOTAL = Counter(
    "wasla_slow_queries_total",
    "Total slow SQL queries detected",
    ["path"],
)

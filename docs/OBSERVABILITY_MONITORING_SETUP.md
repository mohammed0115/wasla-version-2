# Observability Monitoring Setup (Production)

## 1) Environment Configuration
Set these environment variables in production:

```env
# Logging
OBS_LOG_LEVEL=INFO
WASLA_REQUEST_LOG_LEVEL=INFO
WASLA_PERFORMANCE_LOG_LEVEL=INFO

# Sentry
SENTRY_DSN=https://<key>@sentry.io/<project>
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1

# Performance
PERFORMANCE_SLOW_THRESHOLD_MS=500
PERFORMANCE_SLOW_QUERY_THRESHOLD_MS=250
PERFORMANCE_LOG_PERSIST_ENABLED=1
```

## 2) Endpoints
- Health: `/healthz`
- Readiness: `/readyz` (checks DB, cache, Redis, Celery)
- Prometheus: `/metrics`

## 3) Prometheus Scrape Example

```yaml
scrape_configs:
  - job_name: wasla
    metrics_path: /metrics
    static_configs:
      - targets: ["w-sala.com"]
```

## 4) Sentry Integration
Sentry is initialized automatically in `apps.observability.apps.ObservabilityConfig.ready()` when `SENTRY_DSN` is set.

Captured:
- Django unhandled errors
- Celery task errors
- Redis integration signals

Data safety:
- `send_default_pii=False`
- Sensitive values are redacted in JSON logs

## 5) Structured JSON Logging
Log formatter: `apps.observability.logging.JSONFormatter`

Fields include:
- `timestamp`, `level`, `logger`, `message`
- request context (`request_id`, `tenant_id`, `user_id`, `path`, `method`)
- performance fields (`latency_ms`, `query_count`, `cache_status`)

Redaction rules remove values that look like:
- passwords
- tokens
- API keys
- authorization headers

## 6) Slow Query Logging
Slow queries are logged by `apps.observability.middleware.timing.TimingMiddleware` when query time exceeds `PERFORMANCE_SLOW_QUERY_THRESHOLD_MS`.

Event name:
- `slow_query`

Includes:
- duration
- endpoint path
- query signature (truncated)

## 7) Operational Verification
Run after deployment:

```bash
curl -s https://w-sala.com/healthz
curl -s https://w-sala.com/readyz
curl -s https://w-sala.com/metrics | head -n 30
```

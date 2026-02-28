# Wasla Alert Rules (Prometheus)

## Availability

```yaml
groups:
  - name: wasla-availability
    rules:
      - alert: WaslaReadyDegraded
        expr: up{job="wasla"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Wasla target down"
          description: "Prometheus cannot scrape Wasla /metrics endpoint."
```

## Error Rate

```yaml
groups:
  - name: wasla-errors
    rules:
      - alert: WaslaHigh5xxRate
        expr: |
          sum(rate(wasla_http_requests_total{status=~"5.."}[5m]))
          /
          sum(rate(wasla_http_requests_total[5m])) > 0.05
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High 5xx rate"
          description: "5xx ratio above 5% for 10 minutes."
```

## Latency

```yaml
groups:
  - name: wasla-latency
    rules:
      - alert: WaslaHighP95Latency
        expr: |
          histogram_quantile(0.95, sum(rate(wasla_http_request_latency_ms_bucket[5m])) by (le)) > 1000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High request latency"
          description: "p95 request latency above 1000ms."
```

## Slow Queries

```yaml
groups:
  - name: wasla-db
    rules:
      - alert: WaslaSlowQueriesSpiking
        expr: sum(rate(wasla_slow_queries_total[5m])) > 5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Slow queries spike"
          description: "Slow query rate is above threshold."
```

## Alert Routing Guidance
- `critical`: PagerDuty / phone escalation
- `warning`: Slack + incident ticket
- Link alerts to Sentry issue dashboards and runbooks

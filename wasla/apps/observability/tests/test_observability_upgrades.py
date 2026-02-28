from __future__ import annotations

import logging
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.observability.logging import JSONFormatter


class ObservabilityUpgradesTests(TestCase):
    def test_metrics_endpoint_prometheus_format(self):
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("# HELP wasla_http_requests_total", body)
        self.assertIn("# TYPE wasla_http_request_latency_ms histogram", body)

    @override_settings(CACHE_REDIS_URL="redis://localhost:6379/1")
    @patch("redis.from_url")
    @patch("apps.observability.views.health.celery_app.control.inspect")
    def test_readyz_checks_db_redis_celery(self, inspect_mock, redis_from_url_mock):
        redis_client = redis_from_url_mock.return_value
        redis_client.ping.return_value = True

        inspector = inspect_mock.return_value
        inspector.ping.return_value = {"worker@node": {"ok": "pong"}}

        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["db"])
        self.assertTrue(payload["redis"])
        self.assertTrue(payload["celery"])

    def test_json_formatter_redacts_sensitive_values(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="wasla.request",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Authorization: Bearer supersecrettoken",
            args=(),
            exc_info=None,
        )
        record.password = "TopSecret!"

        output = formatter.format(record)
        self.assertIn("[REDACTED]", output)
        self.assertNotIn("supersecrettoken", output)
        self.assertNotIn("TopSecret!", output)

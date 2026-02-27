from __future__ import annotations

import json
from io import StringIO

from django.core.management import call_command

from apps.observability.models import PerformanceBenchmarkReport


def test_check_performance_save_report_persists(db):
    before = PerformanceBenchmarkReport.objects.count()

    call_command(
        "check_performance",
        "--runs", "1",
        "--profile", "default",
        "--host", "localhost",
        "--save-report",
    )

    after = PerformanceBenchmarkReport.objects.count()
    assert after == before + 1


def test_check_performance_json_output_shape(db):
    output = StringIO()
    call_command(
        "check_performance",
        "--runs", "1",
        "--profile", "default",
        "--json",
        stdout=output,
    )
    payload = json.loads(output.getvalue())
    assert isinstance(payload, list)
    assert payload
    first = payload[0]
    assert "endpoint" in first
    assert "avg_duration_ms" in first
    assert "query_count" in first

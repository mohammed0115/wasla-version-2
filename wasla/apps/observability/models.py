from __future__ import annotations

from django.db import models


class RequestPerformanceLog(models.Model):
    request_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    store_id = models.IntegerField(db_index=True)
    endpoint = models.CharField(max_length=255, db_index=True)
    method = models.CharField(max_length=10)
    status_code = models.PositiveIntegerField()
    response_time_ms = models.FloatField()
    db_query_count = models.PositiveIntegerField(default=0)
    cache_hit = models.BooleanField(default=False)
    is_slow = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "created_at"]),
            models.Index(fields=["endpoint", "created_at"]),
            models.Index(fields=["store_id", "endpoint", "created_at"]),
        ]


class PerformanceBenchmarkReport(models.Model):
    profile = models.CharField(max_length=64, default="default", db_index=True)
    host = models.CharField(max_length=255, blank=True, default="")
    runs_per_endpoint = models.PositiveIntegerField(default=1)
    slow_threshold_ms = models.FloatField(default=500.0)
    summary = models.JSONField(default=dict, blank=True)
    report = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class PerformanceLog(models.Model):
    path = models.CharField(max_length=255, db_index=True)
    method = models.CharField(max_length=10)
    store = models.IntegerField(db_index=True)
    duration_ms = models.FloatField(db_index=True)
    query_count = models.PositiveIntegerField(default=0)
    status_code = models.PositiveIntegerField()
    request_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["store", "created_at"]),
            models.Index(fields=["path", "created_at"]),
            models.Index(fields=["duration_ms", "created_at"]),
        ]


class PerformanceReport(models.Model):
    run_at = models.DateTimeField(auto_now_add=True, db_index=True)
    summary_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, default="ok", db_index=True)

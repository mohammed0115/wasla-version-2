from __future__ import annotations

from django.db import models


class WebhookEvent(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_PROCESSED = "PROCESSED"
    STATUS_FAILED = "FAILED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSED, "Processed"),
        (STATUS_FAILED, "Failed"),
    ]

    provider_code = models.CharField(max_length=50)
    event_id = models.CharField(max_length=120)
    idempotency_key = models.CharField(max_length=180, unique=True)
    payload_json = models.JSONField(default=dict, blank=True)
    payload_raw = models.TextField(blank=True, default="")
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    class Meta:
        indexes = [
            models.Index(fields=["provider_code", "event_id"]),
            models.Index(fields=["processing_status", "received_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider_code}:{self.event_id}"

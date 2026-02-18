from __future__ import annotations

from django.conf import settings
from django.db import models


class TenantSmsSettings(models.Model):
    PROVIDER_CONSOLE = "console"
    PROVIDER_TAQNYAT = "taqnyat"

    PROVIDER_CHOICES = [
        (PROVIDER_CONSOLE, "Console (dev)"),
        (PROVIDER_TAQNYAT, "Taqnyat"),
    ]

    tenant = models.OneToOneField(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="sms_settings",
    )
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES, default=PROVIDER_CONSOLE)
    is_enabled = models.BooleanField(default=False)
    sender_name = models.CharField(max_length=50, blank=True, default="")
    config = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["provider", "is_enabled"]),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant.slug}:{self.provider}:{'on' if self.is_enabled else 'off'}"


class SmsMessageLog(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_SENT = "sent"
    STATUS_SCHEDULED = "scheduled"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_SENT, "Sent"),
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_FAILED, "Failed"),
    ]

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_logs",
    )
    provider = models.CharField(max_length=32, default="")
    sender = models.CharField(max_length=50, default="")
    body = models.TextField()
    recipients = models.JSONField(default=list, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    provider_message_id = models.CharField(max_length=128, blank=True, default="")
    provider_response = models.JSONField(blank=True, default=dict)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["provider", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"SmsMessageLog(provider={self.provider}, status={self.status}, created_at={self.created_at})"


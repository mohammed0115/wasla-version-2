from __future__ import annotations

from django.conf import settings
from django.db import models


class SecurityAuditLog(models.Model):
    EVENT_LOGIN = "login"
    EVENT_OTP = "otp"
    EVENT_PAYMENT = "payment"
    EVENT_ADMIN_2FA = "admin_2fa"
    EVENT_RATE_LIMIT = "rate_limit"

    EVENT_CHOICES = [
        (EVENT_LOGIN, "Login"),
        (EVENT_OTP, "OTP"),
        (EVENT_PAYMENT, "Payment"),
        (EVENT_ADMIN_2FA, "Admin2FA"),
        (EVENT_RATE_LIMIT, "RateLimit"),
    ]

    OUTCOME_SUCCESS = "success"
    OUTCOME_FAILURE = "failure"
    OUTCOME_BLOCKED = "blocked"

    OUTCOME_CHOICES = [
        (OUTCOME_SUCCESS, "Success"),
        (OUTCOME_FAILURE, "Failure"),
        (OUTCOME_BLOCKED, "Blocked"),
    ]

    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES)
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="security_audit_logs",
    )
    path = models.CharField(max_length=255, blank=True, default="")
    method = models.CharField(max_length=12, blank=True, default="")
    ip_address = models.CharField(max_length=64, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "created_at"]),
            models.Index(fields=["outcome", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type}:{self.outcome}:{self.path}"

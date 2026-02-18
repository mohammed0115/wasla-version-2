from __future__ import annotations

from django.db import models


class TenantEmailSettings(models.Model):
    PROVIDER_SMTP = "smtp"
    PROVIDER_SENDGRID = "sendgrid"
    PROVIDER_MAILGUN = "mailgun"
    PROVIDER_SES = "ses"

    PROVIDER_CHOICES = [
        (PROVIDER_SMTP, "SMTP"),
        (PROVIDER_SENDGRID, "SendGrid"),
        (PROVIDER_MAILGUN, "Mailgun"),
        (PROVIDER_SES, "AWS SES"),
    ]

    tenant = models.OneToOneField("tenants.Tenant", on_delete=models.CASCADE, related_name="email_settings")
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default=PROVIDER_SMTP)
    from_email = models.EmailField(blank=True, default="")
    from_name = models.CharField(max_length=120, blank=True, default="")
    credentials_encrypted = models.TextField(blank=True, default="")
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["provider", "is_enabled"]),
        ]

    def __str__(self) -> str:
        return f"TenantEmailSettings(tenant_id={self.tenant_id}, provider={self.provider})"


class GlobalEmailSettings(models.Model):
    PROVIDER_SMTP = "smtp"
    PROVIDER_SENDGRID = "sendgrid"
    PROVIDER_MAILGUN = "mailgun"
    PROVIDER_SES = "ses"

    PROVIDER_CHOICES = [
        (PROVIDER_SMTP, "SMTP"),
        (PROVIDER_SENDGRID, "SendGrid"),
        (PROVIDER_MAILGUN, "Mailgun"),
        (PROVIDER_SES, "AWS SES"),
    ]

    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default=PROVIDER_SMTP)
    host = models.CharField(max_length=255, blank=True, default="")
    port = models.PositiveIntegerField(default=587)
    username = models.CharField(max_length=255, blank=True, default="")
    password_encrypted = models.TextField(blank=True, default="")
    from_email = models.EmailField(blank=True, default="")
    use_tls = models.BooleanField(default=True)
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["provider", "enabled"]),
        ]

    def __str__(self) -> str:
        return f"GlobalEmailSettings(provider={self.provider}, enabled={self.enabled})"


class GlobalEmailSettingsAuditLog(models.Model):
    action = models.CharField(max_length=64)
    actor = models.CharField(max_length=150, blank=True, default="system")
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"GlobalEmailSettingsAuditLog(action={self.action})"


class EmailLog(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_SENDING = "sending"
    STATUS_SENT = "sent"
    STATUS_DELIVERED = "delivered"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_SENDING, "Sending"),
        (STATUS_SENT, "Sent"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_FAILED, "Failed"),
    ]

    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE, related_name="email_logs")
    to_email = models.EmailField()
    template_key = models.CharField(max_length=80)
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED, db_index=True)
    provider = models.CharField(max_length=20, blank=True, default="")
    provider_message_id = models.CharField(max_length=255, blank=True, default="")
    idempotency_key = models.CharField(max_length=64)
    last_error = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "idempotency_key"], name="uniq_email_idempotency_per_tenant"),
        ]
        indexes = [
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["tenant", "status", "created_at"]),
            models.Index(fields=["template_key", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"EmailLog(id={self.id}, tenant_id={self.tenant_id}, to={self.to_email}, status={self.status})"

"""
Domain monitoring models for tracking domain health and SSL certificate status.

Models:
- DomainHealth: Track DNS, HTTP, and SSL certificate status
- DomainAlert: Store health check alerts and notifications
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from django.db import models
from django.utils import timezone

from apps.tenants.models import StoreDomain, Tenant


class DomainHealth(models.Model):
    """Track the health status of a domain including DNS, HTTP, and SSL checks."""

    STATUS_HEALTHY = "HEALTHY"
    STATUS_WARNING = "WARNING"
    STATUS_ERROR = "ERROR"

    STATUS_CHOICES = [
        (STATUS_HEALTHY, "Healthy"),
        (STATUS_WARNING, "Warning"),
        (STATUS_ERROR, "Error"),
    ]

    # Relationships
    store_domain = models.OneToOneField(
        StoreDomain,
        on_delete=models.CASCADE,
        related_name="health_status",
        primary_key=True,
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="domain_health_records",
        db_index=True,
    )

    # Health check results
    dns_resolves = models.BooleanField(default=False)
    http_reachable = models.BooleanField(default=False)
    ssl_valid = models.BooleanField(default=False)

    # SSL Certificate tracking
    ssl_expires_at = models.DateTimeField(null=True, blank=True)
    days_until_expiry = models.IntegerField(null=True, blank=True)

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_HEALTHY,
        db_index=True,
    )

    last_checked_at = models.DateTimeField(auto_now_add=True)
    last_error = models.TextField(null=True, blank=True)

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "status"], name="domhealth_tenant_status_idx"),
            models.Index(fields=["status", "last_checked_at"], name="domhealth_status_checked_idx"),
            models.Index(fields=["ssl_expires_at"], name="domhealth_ssl_expiry_idx"),
        ]
        verbose_name_plural = "Domain Health Records"

    def __str__(self) -> str:
        return f"{self.store_domain.domain} - {self.status}"

    def refresh_from_db(self, *_, **__):
        """Override to update days_until_expiry on refresh."""
        super().refresh_from_db()
        self._update_days_until_expiry()

    def _update_days_until_expiry(self) -> None:
        """Recalculate days until SSL expiry."""
        if self.ssl_expires_at and self.ssl_valid:
            now = timezone.now()
            delta = self.ssl_expires_at - now
            self.days_until_expiry = delta.days
        else:
            self.days_until_expiry = None

    def save(self, *args, **kwargs):
        """Update days_until_expiry before saving."""
        self._update_days_until_expiry()
        super().save(*args, **kwargs)

    @property
    def is_expiring_soon(self) -> bool:
        """Check if SSL certificate expires within 30 days."""
        if self.days_until_expiry is None:
            return False
        return 0 < self.days_until_expiry <= 30

    @property
    def is_expired(self) -> bool:
        """Check if SSL certificate has already expired."""
        if self.days_until_expiry is None:
            return False
        return self.days_until_expiry < 0

    @property
    def health_summary(self) -> dict:
        """Return a formatted health summary."""
        return {
            "domain": self.store_domain.domain,
            "store_id": self.tenant_id,
            "status": self.status,
            "dns_resolves": self.dns_resolves,
            "http_reachable": self.http_reachable,
            "ssl_valid": self.ssl_valid,
            "days_until_expiry": self.days_until_expiry,
            "is_expiring_soon": self.is_expiring_soon,
            "is_expired": self.is_expired,
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "last_error": self.last_error or "",
        }

    @property
    def store(self):
        return self.tenant

    @property
    def domain(self):
        return self.store_domain


class DomainAlert(models.Model):
    """Store alerts and notifications about domain health issues."""

    SEVERITY_INFO = "INFO"
    SEVERITY_WARNING = "WARNING"
    SEVERITY_CRITICAL = "CRITICAL"

    SEVERITY_CHOICES = [
        (SEVERITY_INFO, "Informational"),
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_CRITICAL, "Critical"),
    ]

    # Relationships
    store_domain = models.ForeignKey(
        StoreDomain,
        on_delete=models.CASCADE,
        related_name="alerts",
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="domain_alerts",
        db_index=True,
    )

    # Alert data
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default=SEVERITY_WARNING,
        db_index=True,
    )
    message = models.TextField()
    resolution_text = models.TextField(blank=True, default="")

    # Status
    resolved = models.BooleanField(default=False, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.CharField(max_length=100, blank=True, default="")  # "system" or user info

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "resolved"], name="domalert_tenant_resolved_idx"),
            models.Index(fields=["severity", "created_at"], name="domalert_severity_created_idx"),
            models.Index(fields=["store_domain", "resolved"], name="domalert_domain_resolved_idx"),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{self.severity}] {self.store_domain.domain}: {self.message[:50]}"

    def mark_resolved(self, resolved_by: str = "system") -> None:
        """Mark alert as resolved."""
        self.resolved = True
        self.resolved_at = timezone.now()
        self.resolved_by = resolved_by
        self.save(update_fields=["resolved", "resolved_at", "resolved_by", "updated_at"])

    @property
    def store(self):
        return self.tenant

    @property
    def domain(self):
        return self.store_domain

    @classmethod
    def create_from_health(
        cls,
        domain_health: DomainHealth,
        severity: str,
        message: str,
        resolution_text: str = "",
    ) -> DomainAlert:
        """Factory method to create alert from DomainHealth status."""
        # Check if unresolved alert with same message already exists
        existing = (
            cls.objects.filter(
                store_domain=domain_health.store_domain,
                severity=severity,
                message=message,
                resolved=False,
            )
            .order_by("-created_at")
            .first()
        )

        if existing:
            # Update existing alert to keep it fresh
            existing.updated_at = timezone.now()
            existing.save(update_fields=["updated_at"])
            return existing

        # Create new alert
        return cls.objects.create(
            store_domain=domain_health.store_domain,
            tenant=domain_health.tenant,
            severity=severity,
            message=message,
            resolution_text=resolution_text,
        )

    @classmethod
    def create_for_domain(
        cls,
        *,
        store_domain: StoreDomain,
        tenant: Tenant,
        severity: str,
        message: str,
        resolution_text: str = "",
    ) -> DomainAlert:
        existing = (
            cls.objects.filter(
                store_domain=store_domain,
                severity=severity,
                message=message,
                resolved=False,
            )
            .order_by("-created_at")
            .first()
        )
        if existing:
            existing.updated_at = timezone.now()
            existing.save(update_fields=["updated_at"])
            return existing

        return cls.objects.create(
            store_domain=store_domain,
            tenant=tenant,
            severity=severity,
            message=message,
            resolution_text=resolution_text,
        )

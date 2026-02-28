"""PDPL privacy models for data export and account deletion."""

import json
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta


User = get_user_model()


class DataExportRequest(models.Model):
    """Track data export requests (PDPL Article 6)."""

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_PENDING, _("Pending")),
        (STATUS_PROCESSING, _("Processing")),
        (STATUS_COMPLETED, _("Completed")),
        (STATUS_FAILED, _("Failed")),
        (STATUS_EXPIRED, _("Expired")),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="data_export_requests",
    )

    request_id = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Unique request identifier"),
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    format_type = models.CharField(
        max_length=20,
        choices=[
            ("json", _("JSON")),
            ("csv", _("CSV")),
            ("xml", _("XML")),
        ],
        default="json",
        help_text=_("Data export format"),
    )

    requested_at = models.DateTimeField(auto_now_add=True)

    processed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("When export was generated"),
    )

    expires_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("When download link expires (30 days)"),
    )

    download_count = models.IntegerField(
        default=0,
        help_text=_("Number of times downloaded"),
    )

    data_file = models.FileField(
        upload_to="privacy/data_exports/",
        blank=True,
        help_text=_("Generated data export file"),
    )

    file_size = models.BigIntegerField(
        default=0,
        help_text=_("Size of export file in bytes"),
    )

    included_data = models.JSONField(
        default=dict,
        help_text=_("List of data categories included"),
    )

    error_message = models.TextField(
        blank=True,
        help_text=_("Error details if processing failed"),
    )

    notes = models.TextField(
        blank=True,
        help_text=_("Admin notes"),
    )

    class Meta:
        db_table = "privacy_data_export_request"
        verbose_name = _("Data Export Request")
        verbose_name_plural = _("Data Export Requests")
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["request_id"]),
            models.Index(fields=["status", "requested_at"]),
        ]
        ordering = ["-requested_at"]

    def __str__(self):
        return f"Export #{self.request_id} - {self.user.email}"

    def is_expired(self):
        """Check if download link is expired."""
        return self.expires_at and timezone.now() > self.expires_at

    def is_accessible(self):
        """Check if export is still accessible for download."""
        return (
            self.status == self.STATUS_COMPLETED
            and not self.is_expired()
        )


class AccountDeletionRequest(models.Model):
    """Track account deletion requests (PDPL Article 5)."""

    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, _("Pending Confirmation")),
        (STATUS_CONFIRMED, _("Confirmed")),
        (STATUS_PROCESSING, _("Processing")),
        (STATUS_COMPLETED, _("Completed")),
        (STATUS_REJECTED, _("Rejected")),
        (STATUS_CANCELLED, _("Cancelled")),
    ]

    REASON_CHOICES = [
        ("no_longer_needed", _("No longer needed")),
        ("privacy_concerns", _("Privacy concerns")),
        ("found_alternative", _("Found alternative")),
        ("other", _("Other")),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="deletion_request",
    )

    request_id = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Unique request identifier"),
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    reason = models.CharField(
        max_length=50,
        choices=REASON_CHOICES,
        default="other",
    )

    confirmation_code = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Code sent to email for confirmation"),
    )

    is_confirmed = models.BooleanField(
        default=False,
        help_text=_("User confirmed deletion via email link"),
    )

    requested_at = models.DateTimeField(auto_now_add=True)

    confirmed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("When user confirmed deletion"),
    )

    processed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("When account was deleted"),
    )

    grace_period_ends_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("Grace period before irreversible deletion (14 days)"),
    )

    data_backup = models.FileField(
        upload_to="privacy/deletion_backups/",
        blank=True,
        help_text=_("Backup of user data before deletion"),
    )

    reason_details = models.TextField(
        blank=True,
        help_text=_("Additional reason details"),
    )

    notes = models.TextField(
        blank=True,
        help_text=_("Admin notes"),
    )

    is_irreversible = models.BooleanField(
        default=False,
        help_text=_("Account fully deleted and unrecoverable"),
    )

    class Meta:
        db_table = "privacy_account_deletion_request"
        verbose_name = _("Account Deletion Request")
        verbose_name_plural = _("Account Deletion Requests")
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["request_id"]),
            models.Index(fields=["status", "requested_at"]),
        ]
        ordering = ["-requested_at"]

    def __str__(self):
        return f"Deletion #{self.request_id} - {self.user.email}"

    def is_in_grace_period(self):
        """Check if account is in grace period."""
        return (
            self.grace_period_ends_at
            and timezone.now() < self.grace_period_ends_at
        )

    def can_cancel(self):
        """Check if deletion can be cancelled."""
        return (
            self.status in [
                self.STATUS_CONFIRMED,
                self.STATUS_PROCESSING,
            ]
            and self.is_in_grace_period()
        )


class DataAccessLog(models.Model):
    """Audit trail for user data access (PDPL Article 7)."""

    ACTION_CHOICES = [
        ("view", _("View User Data")),
        ("export", _("Export Data")),
        ("download", _("Download Export")),
        ("delete", _("Delete Account")),
        ("restore", _("Restore Account")),
        ("consent_grant", _("Grant Consent")),
        ("consent_revoke", _("Revoke Consent")),
        ("login", _("User Login")),
        ("password_change", _("Password Change")),
        ("email_change", _("Email Change")),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="data_access_logs",
    )

    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
    )

    accessed_by = models.CharField(
        max_length=100,
        help_text=_("Who accessed (user, admin, system)"),
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text=_("IP address of accessor"),
    )

    user_agent = models.TextField(
        blank=True,
        help_text=_("Browser/device info"),
    )

    data_categories = models.JSONField(
        default=list,
        help_text=_("Which data was accessed"),
    )

    purpose = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Purpose of access"),
    )

    details = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Additional details"),
    )

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "privacy_data_access_log"
        verbose_name = _("Data Access Log")
        verbose_name_plural = _("Data Access Logs")
        indexes = [
            models.Index(fields=["user", "action"]),
            models.Index(fields=["timestamp"]),
            models.Index(fields=["accessed_by"]),
        ]
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.user.email} - {self.get_action_display()} - {self.timestamp}"


class ConsentRecord(models.Model):
    """Track user consent to data processing (PDPL compliance)."""

    CONSENT_TYPE_CHOICES = [
        ("marketing", _("Marketing Communications")),
        ("analytics", _("Analytics & Tracking")),
        ("third_party", _("Third-party Sharing")),
        ("profiling", _("Profiling & Personalization")),
        ("cookies", _("Cookies & Similar Tech")),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="consent_records",
    )

    consent_type = models.CharField(
        max_length=30,
        choices=CONSENT_TYPE_CHOICES,
    )

    is_granted = models.BooleanField(
        help_text=_("User granted or revoked this consent"),
    )

    granted_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("When consent was given"),
    )

    revoked_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("When consent was revoked"),
    )

    version = models.CharField(
        max_length=20,
        default="1.0",
        help_text=_("Version of privacy policy agreed to"),
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text=_("IP when consent given"),
    )

    user_agent = models.TextField(
        blank=True,
        help_text=_("Device info for audit"),
    )

    method = models.CharField(
        max_length=50,
        choices=[
            ("checkbox", _("Checkbox")),
            ("explicit", _("Explicit Agreement")),
            ("email", _("Email Confirmation")),
            ("phone", _("Phone Confirmation")),
        ],
        default="checkbox",
    )

    notes = models.TextField(
        blank=True,
        help_text=_("Additional context"),
    )

    class Meta:
        db_table = "privacy_consent_record"
        verbose_name = _("Consent Record")
        verbose_name_plural = _("Consent Records")
        unique_together = ("user", "consent_type")
        indexes = [
            models.Index(fields=["user", "consent_type"]),
            models.Index(fields=["is_granted"]),
        ]

    def __str__(self):
        status = "✓ Granted" if self.is_granted else "✗ Revoked"
        return f"{self.user.email} - {self.get_consent_type_display()} - {status}"

    def is_active(self):
        """Check if consent is currently active."""
        return self.is_granted and (not self.revoked_at or self.granted_at > self.revoked_at)

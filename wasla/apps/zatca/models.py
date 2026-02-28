"""ZATCA models for e-invoicing and digital signatures."""

from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator

from apps.stores.models import Store
from apps.orders.models import Order


class ZatcaCertificate(models.Model):
    """Store ZATCA digital certificate for signing invoices."""

    CERTIFICATE_STATUS_ACTIVE = "active"
    CERTIFICATE_STATUS_EXPIRED = "expired"
    CERTIFICATE_STATUS_REVOKED = "revoked"

    CERTIFICATE_STATUS_CHOICES = [
        (CERTIFICATE_STATUS_ACTIVE, _("Active")),
        (CERTIFICATE_STATUS_EXPIRED, _("Expired")),
        (CERTIFICATE_STATUS_REVOKED, _("Revoked")),
    ]

    store = models.OneToOneField(
        Store,
        on_delete=models.CASCADE,
        related_name="zatca_certificate",
        help_text=_("Certificate is unique per store"),
    )

    certificate_content = models.TextField(
        help_text=_("PEM-encoded X.509 certificate (public)"),
    )

    private_key_content = models.TextField(
        help_text=_("PEM-encoded private key (encrypted)"),
        db_column="private_key_encrypted",
    )

    certificate_serial = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Certificate serial number from ZATCA"),
    )

    common_name = models.CharField(
        max_length=255,
        help_text=_("Certificate common name (e.g., company name)"),
    )

    organization = models.CharField(
        max_length=255,
        help_text=_("Organization name from certificate"),
    )

    expires_at = models.DateTimeField(
        help_text=_("Certificate expiration date"),
    )

    issued_at = models.DateTimeField(
        help_text=_("Certificate issue date"),
    )

    status = models.CharField(
        max_length=20,
        choices=CERTIFICATE_STATUS_CHOICES,
        default=CERTIFICATE_STATUS_ACTIVE,
    )

    approval_id = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("ZATCA approval ID"),
    )

    auth_token = models.TextField(
        blank=True,
        help_text=_("ZATCA authentication token"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "zatca_certificate"
        verbose_name = _("ZATCA Certificate")
        verbose_name_plural = _("ZATCA Certificates")
        indexes = [
            models.Index(fields=["store", "status"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.store.name} - {self.common_name}"

    def is_valid(self):
        """Check if certificate is valid and active."""
        from django.utils import timezone

        return (
            self.status == self.CERTIFICATE_STATUS_ACTIVE
            and self.expires_at > timezone.now()
        )


class ZatcaInvoice(models.Model):
    """ZATCA e-invoice record for order."""

    STATUS_DRAFT = "draft"
    STATUS_ISSUED = "issued"
    STATUS_SUBMITTED = "submitted"
    STATUS_REPORTED = "reported"
    STATUS_CLEARED = "cleared"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_DRAFT, _("Draft")),
        (STATUS_ISSUED, _("Issued")),
        (STATUS_SUBMITTED, _("Submitted to ZATCA")),
        (STATUS_REPORTED, _("Reported")),
        (STATUS_CLEARED, _("Cleared by ZATCA")),
        (STATUS_REJECTED, _("Rejected")),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="zatca_invoice",
    )

    invoice_number = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Unique invoice number (e.g., INV-2024-001)"),
    )

    invoice_date = models.DateField(
        auto_now_add=True,
        help_text=_("Invoice date (date of supply)"),
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )

    xml_content = models.TextField(
        blank=True,
        help_text=_("Generated XML invoice in UBL format"),
    )

    xml_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text=_("SHA256 hash of XML (for clearing)"),
    )

    digital_signature = models.TextField(
        blank=True,
        help_text=_("Digital signature of invoice"),
    )

    qr_code_content = models.TextField(
        blank=True,
        help_text=_("QR code data string"),
    )

    qr_code_image = models.ImageField(
        upload_to="zatca/qr_codes/",
        blank=True,
        help_text=_("Generated QR code image"),
    )

    submission_uuid = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("UUID from ZATCA submission"),
    )

    submission_timestamp = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("When invoice was submitted to ZATCA"),
    )

    clearance_number = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("ZATCA clearance number"),
    )

    clearance_timestamp = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("When invoice was cleared by ZATCA"),
    )

    response_data = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Full ZATCA API response"),
    )

    error_message = models.TextField(
        blank=True,
        help_text=_("Error details if rejected"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "zatca_invoice"
        verbose_name = _("ZATCA Invoice")
        verbose_name_plural = _("ZATCA Invoices")
        indexes = [
            models.Index(fields=["order", "status"]),
            models.Index(fields=["invoice_number"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.order.email}"

    def generate_invoice_number(self):
        """Generate unique invoice number if not set."""
        if not self.invoice_number:
            import uuid

            year = self.invoice_date.year if self.invoice_date else 2024
            month = self.invoice_date.month if self.invoice_date else 1
            # Format: INV-YYYYMM-UNIQUEID
            self.invoice_number = f"INV-{year}{month:02d}-{uuid.uuid4().hex[:8].upper()}"

    def is_submitted(self):
        """Check if invoice submitted to ZATCA."""
        return self.status in [
            self.STATUS_SUBMITTED,
            self.STATUS_REPORTED,
            self.STATUS_CLEARED,
        ]

    def is_cleared(self):
        """Check if invoice cleared by ZATCA."""
        return self.status == self.STATUS_CLEARED


class ZatcaInvoiceLog(models.Model):
    """Audit log for ZATCA invoice operations."""

    ACTION_GENERATED = "generated"
    ACTION_SIGNED = "signed"
    ACTION_SUBMITTED = "submitted"
    ACTION_REPORTED = "reported"
    ACTION_CLEARED = "cleared"
    ACTION_REJECTED = "rejected"

    ACTION_CHOICES = [
        (ACTION_GENERATED, _("Generated")),
        (ACTION_SIGNED, _("Signed")),
        (ACTION_SUBMITTED, _("Submitted")),
        (ACTION_REPORTED, _("Reported")),
        (ACTION_CLEARED, _("Cleared")),
        (ACTION_REJECTED, _("Rejected")),
    ]

    invoice = models.ForeignKey(
        ZatcaInvoice,
        on_delete=models.CASCADE,
        related_name="logs",
    )

    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
    )

    status_code = models.CharField(
        max_length=20,
        blank=True,
        help_text=_("HTTP status or API status code"),
    )

    message = models.TextField(
        help_text=_("Operation message or error details"),
    )

    details = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Additional operation details"),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "zatca_invoice_log"
        verbose_name = _("ZATCA Invoice Log")
        verbose_name_plural = _("ZATCA Invoice Logs")
        indexes = [
            models.Index(fields=["invoice", "action"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.get_action_display()}"

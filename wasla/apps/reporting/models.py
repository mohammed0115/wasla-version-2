"""VAT and tax reporting models."""

from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import datetime, timedelta

from apps.stores.models import Store


class VATReport(models.Model):
    """Monthly VAT report for tax authority submission."""

    REPORT_STATUS_DRAFT = "draft"
    REPORT_STATUS_FINALIZED = "finalized"
    REPORT_STATUS_SUBMITTED = "submitted"
    REPORT_STATUS_ACCEPTED = "accepted"
    REPORT_STATUS_REJECTED = "rejected"

    REPORT_STATUS_CHOICES = [
        (REPORT_STATUS_DRAFT, _("Draft")),
        (REPORT_STATUS_FINALIZED, _("Finalized")),
        (REPORT_STATUS_SUBMITTED, _("Submitted")),
        (REPORT_STATUS_ACCEPTED, _("Accepted")),
        (REPORT_STATUS_REJECTED, _("Rejected")),
    ]

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="vat_reports",
    )

    report_number = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("VAT-YYYY-MM format"),
    )

    period_start = models.DateField(
        help_text=_("Report period start date"),
    )

    period_end = models.DateField(
        help_text=_("Report period end date"),
    )

    status = models.CharField(
        max_length=20,
        choices=REPORT_STATUS_CHOICES,
        default=REPORT_STATUS_DRAFT,
    )

    # Financial Figures (All in SAR)
    total_sales = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal(0),
        help_text=_("Total sales/revenue for period"),
    )

    total_vat_collected = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal(0),
        help_text=_("Total VAT collected from customers (15%)"),
    )

    total_vat_paid = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal(0),
        help_text=_("Total VAT paid on purchases (input VAT)"),
    )

    vat_payable = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal(0),
        help_text=_("VAT to remit to authority (collected - paid)"),
    )

    total_refunds = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal(0),
        help_text=_("Total refunded to customers"),
    )

    refund_vat = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal(0),
        help_text=_("VAT on refunds"),
    )

    # Submission Info
    submission_number = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("ZATCA submission reference"),
    )

    submitted_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("When submitted to authority"),
    )

    accepted_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("When accepted by authority"),
    )

    rejection_reason = models.TextField(
        blank=True,
        help_text=_("Reason for rejection if any"),
    )

    # Files
    csv_file = models.FileField(
        upload_to="vat_reports/csv/",
        blank=True,
        help_text=_("CSV export of transactions"),
    )

    xlsx_file = models.FileField(
        upload_to="vat_reports/xlsx/",
        blank=True,
        help_text=_("Excel workbook with detailed data"),
    )

    submission_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Submitted data to authority"),
    )

    response_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Response from authority"),
    )

    notes = models.TextField(
        blank=True,
        help_text=_("Internal notes"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reporting_vat_report"
        verbose_name = _("VAT Report")
        verbose_name_plural = _("VAT Reports")
        indexes = [
            models.Index(fields=["store", "period_start", "period_end"]),
            models.Index(fields=["status", "period_end"]),
        ]
        unique_together = ("store", "period_start", "period_end")
        ordering = ["-period_end"]

    def __str__(self):
        return f"{self.report_number} - {self.store.name}"

    def calculate_vat_figures(self):
        """Calculate VAT payable from collected and paid."""
        self.vat_payable = self.total_vat_collected - self.total_vat_paid
        if self.total_refunds:
            self.vat_payable -= self.refund_vat
        return self.vat_payable

    def is_finalized(self):
        """Check if report is locked."""
        return self.status != self.REPORT_STATUS_DRAFT

    def can_submit(self):
        """Check if report can be submitted."""
        return self.status == self.REPORT_STATUS_FINALIZED


class VATTransactionLog(models.Model):
    """Detailed log of transactions included in VAT report."""

    TRANSACTION_TYPE_SALE = "sale"
    TRANSACTION_TYPE_REFUND = "refund"
    TRANSACTION_TYPE_ADJUSTMENT = "adjustment"

    TRANSACTION_TYPE_CHOICES = [
        (TRANSACTION_TYPE_SALE, _("Sale")),
        (TRANSACTION_TYPE_REFUND, _("Refund")),
        (TRANSACTION_TYPE_ADJUSTMENT, _("Adjustment")),
    ]

    report = models.ForeignKey(
        VATReport,
        on_delete=models.CASCADE,
        related_name="transactions",
    )

    invoice_number = models.CharField(
        max_length=100,
        help_text=_("Related invoice/order ID"),
    )

    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
    )

    transaction_date = models.DateField(
        help_text=_("Date of transaction"),
    )

    amount_ex_vat = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text=_("Amount excluding VAT"),
    )

    vat_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text=_("VAT charged (15% typically)"),
    )

    amount_inc_vat = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text=_("Total amount including VAT"),
    )

    customer_type = models.CharField(
        max_length=20,
        choices=[
            ("b2c", _("Consumer (B2C)")),
            ("b2b", _("Business (B2B)")),
        ],
        default="b2c",
    )

    payment_method = models.CharField(
        max_length=50,
        help_text=_("How payment was made"),
    )

    notes = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reporting_vat_transaction_log"
        verbose_name = _("VAT Transaction Log")
        verbose_name_plural = _("VAT Transaction Logs")
        indexes = [
            models.Index(fields=["report", "transaction_date"]),
            models.Index(fields=["invoice_number"]),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.amount_inc_vat} SAR"


class TaxExemption(models.Model):
    """Track tax-exempt transactions."""

    EXEMPTION_TYPE_CHOICES = [
        ("export", _("Export Sales")),
        ("nonprofit", _("Non-Profit Organization")),
        ("government", _("Government Transaction")),
        ("other", _("Other Exemption")),
    ]

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="tax_exemptions",
    )

    exemption_type = models.CharField(
        max_length=30,
        choices=EXEMPTION_TYPE_CHOICES,
    )

    document_number = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Invoice/order number"),
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text=_("Exempt transaction amount"),
    )

    exemption_date = models.DateField(
        help_text=_("Date of exempt transaction"),
    )

    reason = models.TextField(
        help_text=_("Reason for exemption"),
    )

    documentation = models.FileField(
        upload_to="tax_exemptions/",
        blank=True,
        help_text=_("Supporting documentation"),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reporting_tax_exemption"
        verbose_name = _("Tax Exemption")
        verbose_name_plural = _("Tax Exemptions")
        indexes = [
            models.Index(fields=["store", "exemption_date"]),
        ]

    def __str__(self):
        return f"{self.document_number} - {self.amount} SAR"

"""ZATCA admin configuration."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse

from apps.zatca.models import ZatcaCertificate, ZatcaInvoice, ZatcaInvoiceLog


@admin.register(ZatcaCertificate)
class ZatcaCertificateAdmin(admin.ModelAdmin):
    """ZATCA certificate admin interface."""

    list_display = [
        "store",
        "common_name",
        "status_badge",
        "expires_at",
        "is_valid_check",
        "updated_at",
    ]
    list_filter = [
        "status",
        "expires_at",
        "created_at",
    ]
    search_fields = [
        "store__name",
        "common_name",
        "certificate_serial",
    ]
    readonly_fields = [
        "certificate_serial",
        "created_at",
        "updated_at",
        "certificate_info",
    ]
    fieldsets = (
        (
            _("Store"),
            {
                "fields": ("store",),
            },
        ),
        (
            _("Certificate"),
            {
                "fields": (
                    "status",
                    "common_name",
                    "organization",
                    "certificate_serial",
                ),
            },
        ),
        (
            _("Dates"),
            {
                "fields": ("issued_at", "expires_at"),
            },
        ),
        (
            _("Keys (Encrypted)"),
            {
                "fields": (
                    "certificate_content",
                    "private_key_content",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("ZATCA"),
            {
                "fields": ("approval_id", "webhook_secret", "auth_token"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Audit"),
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    def status_badge(self, obj):
        """Display status with badge."""
        colors = {
            "active": "#4CAF50",
            "expired": "#FFC107",
            "revoked": "#F44336",
        }
        color = colors.get(obj.status, "#999")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = _("Status")

    def is_valid_check(self, obj):
        """Show validity check."""
        is_valid = obj.is_valid()
        status = "✓ Valid" if is_valid else "✗ Invalid"
        color = "green" if is_valid else "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            status,
        )

    is_valid_check.short_description = _("Valid for Signing")

    def certificate_info(self, obj):
        """Display certificate info."""
        return format_html(
            "<p><strong>Serial:</strong> {}</p>"
            "<p><strong>CN:</strong> {}</p>"
            "<p><strong>Organization:</strong> {}</p>"
            "<p><strong>Valid:</strong> {} to {}</p>",
            obj.certificate_serial,
            obj.common_name,
            obj.organization,
            obj.issued_at.strftime("%Y-%m-%d"),
            obj.expires_at.strftime("%Y-%m-%d"),
        )

    certificate_info.short_description = _("Certificate Information")


@admin.register(ZatcaInvoice)
class ZatcaInvoiceAdmin(admin.ModelAdmin):
    """ZATCA invoice admin interface."""

    list_display = [
        "invoice_number",
        "order_link",
        "status_badge",
        "invoice_date",
        "total_amount",
        "tax_amount",
        "created_at",
    ]
    list_filter = [
        "status",
        "invoice_date",
        "created_at",
    ]
    search_fields = [
        "invoice_number",
        "order__id",
        "order__email",
    ]
    readonly_fields = [
        "order",
        "invoice_number",
        "invoice_date",
        "xml_content",
        "xml_hash",
        "digital_signature",
        "qr_code_content",
        "submission_uuid",
        "submission_timestamp",
        "clearance_number",
        "clearance_timestamp",
        "response_data",
        "created_at",
        "updated_at",
        "invoice_logs",
    ]
    fieldsets = (
        (
            _("Order"),
            {
                "fields": ("order", "invoice_number", "invoice_date"),
            },
        ),
        (
            _("Status"),
            {
                "fields": ("status", "error_message"),
            },
        ),
        (
            _("Invoice Content"),
            {
                "fields": ("xml_content", "xml_hash"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Digital Signature"),
            {
                "fields": ("digital_signature",),
                "classes": ("collapse",),
            },
        ),
        (
            _("QR Code"),
            {
                "fields": ("qr_code_content", "qr_code_image"),
                "classes": ("collapse",),
            },
        ),
        (
            _("ZATCA Submission"),
            {
                "fields": (
                    "submission_uuid",
                    "submission_timestamp",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("ZATCA Clearance"),
            {
                "fields": (
                    "clearance_number",
                    "clearance_timestamp",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("API Response"),
            {
                "fields": ("response_data",),
                "classes": ("collapse",),
            },
        ),
        (
            _("Activity Logs"),
            {
                "fields": ("invoice_logs",),
            },
        ),
        (
            _("Audit"),
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    def order_link(self, obj):
        """Link to order."""
        url = reverse("admin:orders_order_change", args=[obj.order.id])
        return format_html(
            '<a href="{}">Order #{}</a>',
            url,
            obj.order.id,
        )

    order_link.short_description = _("Order")

    def status_badge(self, obj):
        """Display status with badge."""
        colors = {
            "draft": "#9E9E9E",
            "issued": "#2196F3",
            "submitted": "#FF9800",
            "reported": "#00BCD4",
            "cleared": "#4CAF50",
            "rejected": "#F44336",
        }
        color = colors.get(obj.status, "#999")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = _("Status")

    def total_amount(self, obj):
        """Display order total."""
        return f"{obj.order.total_amount} {obj.order.currency}"

    total_amount.short_description = _("Total")

    def tax_amount(self, obj):
        """Display tax amount."""
        return f"{obj.order.tax_amount} {obj.order.currency}"

    tax_amount.short_description = _("Tax")

    def invoice_logs(self, obj):
        """Display activity logs."""
        logs = obj.logs.all().order_by("-created_at")[:10]
        if not logs:
            return "No activity yet"

        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += "<tr><th>Action</th><th>Message</th><th>Time</th></tr>"
        for log in logs:
            html += f"<tr><td><strong>{log.get_action_display()}</strong></td><td>{log.message}</td><td>{log.created_at.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>"
        html += "</table>"
        return format_html(html)

    invoice_logs.short_description = _("Activity Logs")


@admin.register(ZatcaInvoiceLog)
class ZatcaInvoiceLogAdmin(admin.ModelAdmin):
    """ZATCA invoice log admin interface."""

    list_display = [
        "invoice_number",
        "action_badge",
        "status_code",
        "short_message",
        "created_at",
    ]
    list_filter = [
        "action",
        "status_code",
        "created_at",
    ]
    search_fields = [
        "invoice__invoice_number",
        "message",
    ]
    readonly_fields = [
        "invoice",
        "action",
        "status_code",
        "message",
        "details",
        "created_at",
    ]
    fieldsets = (
        (
            _("Invoice"),
            {
                "fields": ("invoice",),
            },
        ),
        (
            _("Action"),
            {
                "fields": ("action", "status_code"),
            },
        ),
        (
            _("Details"),
            {
                "fields": ("message", "details"),
            },
        ),
        (
            _("Audit"),
            {
                "fields": ("created_at",),
            },
        ),
    )

    def invoice_number(self, obj):
        """Display invoice number."""
        return obj.invoice.invoice_number

    invoice_number.short_description = _("Invoice")

    def action_badge(self, obj):
        """Display action with badge."""
        colors = {
            "generated": "#2196F3",
            "signed": "#4CAF50",
            "submitted": "#FF9800",
            "reported": "#00BCD4",
            "cleared": "#8BC34A",
            "rejected": "#F44336",
        }
        color = colors.get(obj.action, "#999")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_action_display(),
        )

    action_badge.short_description = _("Action")

    def short_message(self, obj):
        """Display truncated message."""
        return obj.message[:100] + ("..." if len(obj.message) > 100 else "")

    short_message.short_description = _("Message")

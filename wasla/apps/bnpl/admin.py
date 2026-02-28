"""BNPL admin configuration."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.utils.html import format_html
from .models import BnplProvider, BnplTransaction, BnplWebhookLog


@admin.register(BnplProvider)
class BnplProviderAdmin(admin.ModelAdmin):
    """BNPL provider admin interface."""

    list_display = [
        "store",
        "provider_display",
        "is_active",
        "is_sandbox",
        "created_at",
    ]
    list_filter = [
        "provider",
        "is_active",
        "is_sandbox",
        "created_at",
    ]
    search_fields = [
        "store__name",
        "merchant_id",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            _("Store & Provider"),
            {
                "fields": ("store", "provider", "is_active", "is_sandbox"),
            },
        ),
        (
            _("Credentials"),
            {
                "fields": ("merchant_id", "api_key", "secret_key", "webhook_secret"),
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

    def provider_display(self, obj):
        """Display provider name with color."""
        colors = {
            "tabby": "#2E8B9E",
            "tamara": "#00A3E9",
        }
        color = colors.get(obj.provider, "#999")
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_provider_display(),
        )

    provider_display.short_description = _("Provider")


@admin.register(BnplTransaction)
class BnplTransactionAdmin(admin.ModelAdmin):
    """BNPL transaction admin interface."""

    list_display = [
        "id",
        "order_link",
        "provider_display",
        "status_display",
        "amount",
        "installments_display",
        "created_at",
    ]
    list_filter = [
        "provider",
        "status",
        "created_at",
        "created_at",
    ]
    search_fields = [
        "order__id",
        "provider_order_id",
        "customer_email",
        "customer_phone",
    ]
    readonly_fields = [
        "order",
        "provider_order_id",
        "provider_reference",
        "payment_url",
        "checkout_id",
        "response_data",
        "created_at",
        "updated_at",
        "webhook_logs",
    ]
    fieldsets = (
        (
            _("Order"),
            {
                "fields": ("order", "provider"),
            },
        ),
        (
            _("Payment Details"),
            {
                "fields": (
                    "amount",
                    "currency",
                    "installment_count",
                    "installment_amount",
                ),
            },
        ),
        (
            _("Customer"),
            {
                "fields": ("customer_email", "customer_phone"),
            },
        ),
        (
            _("Provider"),
            {
                "fields": (
                    "provider_order_id",
                    "provider_reference",
                    "checkout_id",
                    "payment_url",
                    "status",
                ),
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
            _("Webhooks"),
            {
                "fields": ("webhook_logs",),
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
            '<a href="{}">#{}  ({})</a>',
            url,
            obj.order.id,
            obj.order.email,
        )

    order_link.short_description = _("Order")

    def status_display(self, obj):
        """Display status with color."""
        colors = {
            "pending": "#FFC107",
            "authorized": "#00BCD4",
            "approved": "#4CAF50",
            "rejected": "#F44336",
            "cancelled": "#9E9E9E",
            "paid": "#8BC34A",
            "refunded": "#673AB7",
        }
        color = colors.get(obj.status, "#999")
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_display.short_description = _("Status")

    def installments_display(self, obj):
        """Display installment info."""
        if obj.installment_count:
            return f"{obj.installment_count} × {obj.installment_amount} SAR"
        return "-"

    installments_display.short_description = _("Installments")

    def provider_display(self, obj):
        """Display provider name."""
        return obj.get_provider_display()

    provider_display.short_description = _("Provider")

    def webhook_logs(self, obj):
        """Display webhook logs."""
        logs = obj.webhooklogs.all().order_by("-created_at")[:5]
        if not logs:
            return "No webhooks yet"

        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += "<tr><th>Event</th><th>Status</th><th>Time</th></tr>"
        for log in logs:
            html += f"<tr><td>{log.event_type}</td><td>{log.status}</td><td>{log.created_at.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>"
        html += "</table>"
        return format_html(html)

    webhook_logs.short_description = _("Recent Webhooks")


@admin.register(BnplWebhookLog)
class BnplWebhookLogAdmin(admin.ModelAdmin):
    """BNPL webhook log admin interface."""

    list_display = [
        "id",
        "transaction_link",
        "event_type",
        "status",
        "is_verified",
        "is_processed",
        "created_at",
    ]
    list_filter = [
        "event_type",
        "status",
        "signature_verified",
        "processed",
        "created_at",
    ]
    search_fields = [
        "transaction__provider_order_id",
        "event_type",
    ]
    readonly_fields = [
        "transaction",
        "event_type",
        "status",
        "payload",
        "signature_verified",
        "processed",
        "error_message",
        "created_at",
    ]
    fieldsets = (
        (
            _("Transaction"),
            {
                "fields": ("transaction", "event_type", "status"),
            },
        ),
        (
            _("Verification"),
            {
                "fields": ("signature_verified", "processed"),
            },
        ),
        (
            _("Payload"),
            {
                "fields": ("payload",),
                "classes": ("collapse",),
            },
        ),
        (
            _("Error"),
            {
                "fields": ("error_message",),
                "classes": ("collapse",),
            },
        ),
        (
            _("Audit"),
            {
                "fields": ("created_at",),
            },
        ),
    )

    def transaction_link(self, obj):
        """Link to transaction."""
        url = reverse("admin:bnpl_bnpltransaction_change", args=[obj.transaction.id])
        return format_html(
            '<a href="{}">Order #{} ({})</a>',
            url,
            obj.transaction.order.id,
            obj.transaction.provider,
        )

    transaction_link.short_description = _("Transaction")

    def is_verified(self, obj):
        """Display verification status."""
        status = "✓" if obj.signature_verified else "✗"
        color = "green" if obj.signature_verified else "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            status,
        )

    is_verified.short_description = _("Verified")

    def is_processed(self, obj):
        """Display processed status."""
        status = "✓" if obj.processed else "⏳"
        color = "green" if obj.processed else "orange"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            status,
        )

    is_processed.short_description = _("Processed")

from __future__ import annotations

from django.contrib import admin

from apps.sms.models import SmsMessageLog, TenantSmsSettings


@admin.register(TenantSmsSettings)
class TenantSmsSettingsAdmin(admin.ModelAdmin):
    list_display = ("tenant", "provider", "is_enabled", "sender_name", "updated_at")
    list_filter = ("provider", "is_enabled")
    search_fields = ("tenant__slug", "tenant__name", "sender_name")


@admin.register(SmsMessageLog)
class SmsMessageLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "tenant", "provider", "status", "short_recipients", "scheduled_at")
    list_filter = ("provider", "status", "created_at")
    search_fields = ("provider_message_id", "body")
    readonly_fields = ("created_at", "updated_at")

    @staticmethod
    def short_recipients(obj: SmsMessageLog) -> str:
        recipients = obj.recipients or []
        if not recipients:
            return ""
        text = ", ".join(recipients[:2])
        if len(recipients) > 2:
            text = f"{text} (+{len(recipients) - 2})"
        return text


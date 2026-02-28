"""
Django admin configuration for analytics reports.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from apps.analytics.models_reports import ScheduledReport, ReportLog


@admin.register(ScheduledReport)
class ScheduledReportAdmin(admin.ModelAdmin):
    list_display = [
        'report_type_display',
        'scope_display',
        'frequency',
        'status_display',
        'next_send_at',
        'last_sent_at',
        'actions_display',
    ]
    list_filter = [
        'report_type',
        'frequency',
        'is_active',
        'is_admin',
        'created_at',
    ]
    search_fields = [
        'store_id',
        'email_recipients',
    ]
    readonly_fields = [
        'created_at',
        'updated_at',
        'last_sent_at',
    ]

    fieldsets = (
        ('Report Configuration', {
            'fields': ('report_type', 'frequency', 'delivery_format'),
        }),
        ('Recipients', {
            'fields': ('store_id', 'is_admin', 'email_recipients'),
        }),
        ('Status', {
            'fields': ('is_active', 'next_send_at', 'last_sent_at'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def report_type_display(self, obj):
        return obj.get_report_type_display()
    report_type_display.short_description = 'Report Type'
    report_type_display.admin_order_field = 'report_type'

    def scope_display(self, obj):
        if obj.is_admin:
            return format_html('<span style="color: #e74c3c;"><strong>[ADMIN]</strong> Platform</span>')
        else:
            return format_html('<span style="color: #3498db;">Store {}</span>', obj.store_id or '—')
    scope_display.short_description = 'Scope'

    def status_display(self, obj):
        if obj.is_active:
            return format_html('<span style="color: #27ae60;"><strong>●</strong> Active</span>')
        else:
            return format_html('<span style="color: #95a5a6;"><strong>●</strong> Inactive</span>')
    status_display.short_description = 'Status'

    def actions_display(self, obj):
        from django.contrib.admin import site
        return format_html(
            '<a class="button" href="{}">View Logs</a>',
            f'{reverse("admin:analytics_reportlog_changelist")}?scheduled_report__id__exact={obj.id}',
        )
    actions_display.short_description = 'Actions'

    actions = ['activate_reports', 'deactivate_reports']

    def activate_reports(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} reports activated.')
    activate_reports.short_description = 'Activate selected reports'

    def deactivate_reports(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} reports deactivated.')
    deactivate_reports.short_description = 'Deactivate selected reports'


@admin.register(ReportLog)
class ReportLogAdmin(admin.ModelAdmin):
    list_display = [
        'report_type_display',
        'status_badge',
        'scheduled_report',
        'generated_at',
        'sent_at',
    ]
    list_filter = [
        'status',
        'generated_at',
        'sent_at',
        'scheduled_report__report_type',
    ]
    readonly_fields = [
        'scheduled_report',
        'status',
        'report_data_display',
        'generated_at',
        'sent_at',
        'error_message',
    ]

    fieldsets = (
        ('Report Info', {
            'fields': ('scheduled_report', 'status'),
        }),
        ('Data', {
            'fields': ('report_data_display',),
        }),
        ('Timestamps', {
            'fields': ('generated_at', 'sent_at'),
        }),
        ('Errors', {
            'fields': ('error_message',),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def report_type_display(self, obj):
        return obj.scheduled_report.get_report_type_display()
    report_type_display.short_description = 'Report Type'
    report_type_display.admin_order_field = 'scheduled_report__report_type'

    def status_badge(self, obj):
        colors = {
            'pending': '#f39c12',
            'generated': '#3498db',
            'sent': '#27ae60',
            'failed': '#e74c3c',
        }
        color = colors.get(obj.status, '#95a5a6')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def report_data_display(self, obj):
        import json
        data_json = json.dumps(obj.report_data, indent=2)
        return format_html('<pre style="background-color: #f5f5f5; padding: 10px; border-radius: 4px;">{}</pre>', data_json)
    report_data_display.short_description = 'Report Data (JSON)'

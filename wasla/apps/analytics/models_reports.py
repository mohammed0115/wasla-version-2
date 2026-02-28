"""
Scheduled reports for analytics dashboard.

Generates automated daily/weekly/monthly reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
import csv

from django.db import models
from django.utils import timezone
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from apps.analytics.application.dashboard_services import (
    MerchantDashboardService,
    RevenueChartService,
    FunnelAnalysisService,
    AdminExecutiveDashboardService,
)


# ============================================================================
# Report Models
# ============================================================================

class ScheduledReport(models.Model):
    """Scheduled report configuration."""

    REPORT_TYPE_CHOICES = [
        ('kpi_summary', 'KPI Summary'),
        ('revenue_analysis', 'Revenue Analysis'),
        ('conversion_funnel', 'Conversion Funnel'),
        ('executive_summary', 'Executive Summary (Admin)'),
    ]

    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    DELIVERY_FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('html_email', 'HTML Email'),
        ('json', 'JSON'),
    ]

    # For merchant reports
    store_id = models.IntegerField(null=True, blank=True, db_index=True)
    
    # For admin reports
    is_admin = models.BooleanField(default=False, db_index=True)

    report_type = models.CharField(max_length=50, choices=REPORT_TYPE_CHOICES)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    delivery_format = models.CharField(max_length=20, choices=DELIVERY_FORMAT_CHOICES, default='html_email')

    # Recipients
    email_recipients = models.JSONField(default=list)  # List of email addresses

    # Scheduling
    is_active = models.BooleanField(default=True, db_index=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    next_send_at = models.DateTimeField(db_index=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_active', 'next_send_at']),
            models.Index(fields=['store_id', 'is_active']),
        ]

    def __str__(self) -> str:
        scope = f"Store {self.store_id}" if self.store_id else "Platform"
        return f"{self.get_report_type_display()} - {self.get_frequency_display()} ({scope})"


class ReportLog(models.Model):
    """Log of generated reports."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('generated', 'Generated'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    scheduled_report = models.ForeignKey(ScheduledReport, on_delete=models.CASCADE, related_name='logs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    report_data = models.JSONField(default=dict)
    file_content = models.FileField(upload_to='analytics/reports/', blank=True)

    generated_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self) -> str:
        return f"Report: {self.scheduled_report} ({self.get_status_display()})"


# ============================================================================
# Report Service
# ============================================================================

class ReportService:
    """Service for generating and sending reports."""

    @staticmethod
    def create_scheduled_report(
        report_type: str,
        frequency: str,
        email_recipients: list[str],
        store_id: int | None = None,
        is_admin: bool = False,
        delivery_format: str = 'html_email'
    ) -> ScheduledReport:
        """
        Create a new scheduled report.

        Args:
            report_type: Type of report
            frequency: daily, weekly, or monthly
            email_recipients: List of email addresses
            store_id: Store ID (None for admin)
            is_admin: Whether this is admin report
            delivery_format: Format for delivery

        Returns:
            ScheduledReport object
        """
        next_send = ReportService._calculate_next_send(frequency)

        report = ScheduledReport.objects.create(
            store_id=store_id,
            is_admin=is_admin,
            report_type=report_type,
            frequency=frequency,
            email_recipients=email_recipients,
            delivery_format=delivery_format,
            next_send_at=next_send,
        )
        return report

    @staticmethod
    def _calculate_next_send(frequency: str) -> datetime:
        """Calculate next send time."""
        now = timezone.now()

        if frequency == 'daily':
            # Tomorrow at 8 AM
            tomorrow = now.date() + timedelta(days=1)
            return timezone.make_aware(
                timezone.datetime.combine(tomorrow, timezone.datetime.min.time()).replace(hour=8)
            )
        elif frequency == 'weekly':
            # Next Monday at 8 AM
            days_until_monday = (7 - now.weekday()) % 7 or 7
            next_monday = now.date() + timedelta(days=days_until_monday)
            return timezone.make_aware(
                timezone.datetime.combine(next_monday, timezone.datetime.min.time()).replace(hour=8)
            )
        elif frequency == 'monthly':
            # First day of next month at 8 AM
            if now.month == 12:
                next_month = now.date().replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.date().replace(month=now.month + 1, day=1)
            return timezone.make_aware(
                timezone.datetime.combine(next_month, timezone.datetime.min.time()).replace(hour=8)
            )

        return now

    @staticmethod
    def generate_merchant_report(scheduled_report: ScheduledReport) -> ReportLog:
        """
        Generate a merchant report.

        Args:
            scheduled_report: ScheduledReport object

        Returns:
            ReportLog object
        """
        kpi = MerchantDashboardService.get_merchant_kpis(scheduled_report.store_id)
        chart = RevenueChartService.get_revenue_chart(scheduled_report.store_id, days=30)
        funnel = FunnelAnalysisService.get_conversion_funnel(scheduled_report.store_id, days=7)

        report_data = {
            'report_type': scheduled_report.report_type,
            'generated_at': timezone.now().isoformat(),
            'kpi': {
                'revenue_today': str(kpi.revenue_today),
                'orders_today': kpi.orders_today,
                'conversion_rate': kpi.conversion_rate,
                'revenue_7d': str(kpi.revenue_7d),
                'revenue_30d': str(kpi.revenue_30d),
            },
            'chart': {
                'total_revenue': str(chart.total_revenue),
                'total_orders': chart.total_orders,
                'points_count': len(chart.points),
            },
            'funnel': {
                'product_views': funnel.product_views,
                'add_to_cart': funnel.add_to_cart,
                'checkout_started': funnel.checkout_started,
                'purchase_completed': funnel.purchase_completed,
                'overall_conversion_rate': funnel.overall_conversion_rate,
            }
        }

        log = ReportLog.objects.create(
            scheduled_report=scheduled_report,
            status='generated',
            report_data=report_data,
        )

        return log

    @staticmethod
    def generate_admin_report(scheduled_report: ScheduledReport) -> ReportLog:
        """
        Generate an admin/executive report.

        Args:
            scheduled_report: ScheduledReport object

        Returns:
            ReportLog object
        """
        kpi = AdminExecutiveDashboardService.get_admin_kpis()

        report_data = {
            'report_type': scheduled_report.report_type,
            'generated_at': timezone.now().isoformat(),
            'metrics': {
                'gmv': str(kpi.gmv),
                'mrr': str(kpi.mrr),
                'active_stores': kpi.active_stores,
                'churn_rate': kpi.churn_rate,
                'total_customers': kpi.total_customers,
                'conversion_rate': kpi.conversion_rate,
                'payment_success_rate': kpi.payment_success_rate,
            },
            'top_products': kpi.top_products[:5],
            'top_merchants': kpi.top_merchants[:5],
        }

        log = ReportLog.objects.create(
            scheduled_report=scheduled_report,
            status='generated',
            report_data=report_data,
        )

        return log

    @staticmethod
    def send_report(report_log: ReportLog) -> bool:
        """
        Send report via email.

        Args:
            report_log: ReportLog object

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            scheduled_report = report_log.scheduled_report

            # Generate email content
            context = {
                'report': report_log,
                'report_type': scheduled_report.get_report_type_display(),
                'report_data': report_log.report_data,
            }

            html_content = render_to_string(
                'analytics/report_email.html',
                context
            )

            # Send email
            email = EmailMessage(
                subject=f"Analytics Report: {scheduled_report.get_report_type_display()}",
                body=html_content,
                from_email='noreply@wasla.io',
                to=scheduled_report.email_recipients,
            )
            email.content_subtype = 'html'
            email.send()

            # Update log
            report_log.status = 'sent'
            report_log.sent_at = timezone.now()
            report_log.save()

            # Update scheduled report
            scheduled_report.last_sent_at = timezone.now()
            scheduled_report.next_send_at = ReportService._calculate_next_send(scheduled_report.frequency)
            scheduled_report.save()

            return True

        except Exception as e:
            report_log.status = 'failed'
            report_log.error_message = str(e)
            report_log.save()
            return False

    @staticmethod
    def get_due_reports() -> list[ScheduledReport]:
        """Get all scheduled reports that are due to run."""
        now = timezone.now()
        return list(
            ScheduledReport.objects.filter(
                is_active=True,
                next_send_at__lte=now
            ).order_by('next_send_at')
        )

    @staticmethod
    def export_report_csv(report_log: ReportLog) -> str:
        """
        Export report as CSV.

        Args:
            report_log: ReportLog object

        Returns:
            CSV string
        """
        output = BytesIO()
        writer = csv.writer(output)

        data = report_log.report_data

        # Header
        writer.writerow(['Metric', 'Value'])
        writer.writerow([])

        # Flatten data
        def write_dict(d, prefix=''):
            for key, value in d.items():
                if isinstance(value, dict):
                    write_dict(value, prefix=f"{prefix}{key}_")
                elif isinstance(value, list):
                    writer.writerow([f"{prefix}{key}", f"Count: {len(value)}"])
                else:
                    writer.writerow([f"{prefix}{key}", value])

        write_dict(data)

        return output.getvalue().decode('utf-8')

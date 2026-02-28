"""
Celery tasks for analytics.

Handles scheduled report generation and sending.
"""

from celery import shared_task
from django.utils import timezone

from apps.analytics.models_reports import ScheduledReport, ReportService


@shared_task
def check_and_send_due_reports():
    """
    Check for due scheduled reports and send them.

    This task should be scheduled to run hourly or more frequently.
    """
    due_reports = ReportService.get_due_reports()

    for report in due_reports:
        generate_and_send_report.delay(report.id)


@shared_task
def generate_and_send_report(report_id: int):
    """
    Generate and send a scheduled report.

    Args:
        report_id: ID of ScheduledReport
    """
    try:
        scheduled_report = ScheduledReport.objects.get(id=report_id)

        # Generate report based on type
        if scheduled_report.is_admin:
            report_log = ReportService.generate_admin_report(scheduled_report)
        else:
            report_log = ReportService.generate_merchant_report(scheduled_report)

        # Send report
        ReportService.send_report(report_log)

    except ScheduledReport.DoesNotExist:
        pass
    except Exception as e:
        # Log error but don't fail the task
        print(f"Error generating report {report_id}: {str(e)}")


@shared_task
def cleanup_old_report_logs(days: int = 90):
    """
    Delete old report logs (older than specified days).

    Args:
        days: Number of days to keep
    """
    from apps.analytics.models_reports import ReportLog

    cutoff_date = timezone.now() - timezone.timedelta(days=days)
    deleted_count, _ = ReportLog.objects.filter(generated_at__lt=cutoff_date).delete()
    return f"Deleted {deleted_count} old report logs"

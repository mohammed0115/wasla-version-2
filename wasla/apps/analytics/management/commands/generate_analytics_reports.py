"""
Management command to generate and send analytics reports.

Usage:
    python manage.py generate_analytics_reports          # Send due reports
    python manage.py generate_analytics_reports --all    # Force send all active reports
    python manage.py generate_analytics_reports --id <id> # Send specific report
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.analytics.models_reports import ScheduledReport, ReportService


class Command(BaseCommand):
    help = 'Generate and send analytics reports'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Send all active reports regardless of schedule',
        )
        parser.add_argument(
            '--id',
            type=int,
            help='Send specific report by ID',
        )
        parser.add_argument(
            '--store-id',
            type=int,
            help='Send all reports for specific store',
        )

    def handle(self, *args, **options):
        if options['id']:
            self._send_report_by_id(options['id'])
        elif options['store_id']:
            self._send_store_reports(options['store_id'])
        elif options['all']:
            self._send_all_reports()
        else:
            self._send_due_reports()

    def _send_report_by_id(self, report_id: int):
        """Send specific report by ID."""
        try:
            scheduled_report = ScheduledReport.objects.get(id=report_id)
            self._generate_and_send(scheduled_report)
        except ScheduledReport.DoesNotExist:
            raise CommandError(f'Report {report_id} not found')

    def _send_store_reports(self, store_id: int):
        """Send all reports for a specific store."""
        reports = ScheduledReport.objects.filter(store_id=store_id, is_active=True)
        count = reports.count()
        self.stdout.write(f"Found {count} active reports for store {store_id}")
        for report in reports:
            self._generate_and_send(report)

    def _send_all_reports(self):
        """Send all active reports."""
        reports = ScheduledReport.objects.filter(is_active=True)
        count = reports.count()
        self.stdout.write(f"Found {count} active reports")
        for report in reports:
            self._generate_and_send(report)

    def _send_due_reports(self):
        """Send only due reports."""
        reports = ReportService.get_due_reports()
        count = len(reports)
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No reports due at this time'))
            return
        self.stdout.write(f"Found {count} due reports")
        for report in reports:
            self._generate_and_send(report)

    def _generate_and_send(self, scheduled_report: ScheduledReport):
        """Generate and send a single report."""
        try:
            self.stdout.write(f"Processing: {scheduled_report}")

            # Generate
            if scheduled_report.is_admin:
                report_log = ReportService.generate_admin_report(scheduled_report)
            else:
                report_log = ReportService.generate_merchant_report(scheduled_report)
            self.stdout.write(self.style.SUCCESS(f"  ✓ Generated"))

            # Send
            if ReportService.send_report(report_log):
                self.stdout.write(self.style.SUCCESS(f"  ✓ Sent to {scheduled_report.email_recipients}"))
            else:
                self.stdout.write(self.style.ERROR(f"  ✗ Failed to send"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Error: {str(e)}"))

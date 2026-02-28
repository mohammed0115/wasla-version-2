"""
Celery Beat schedule configuration for analytics reports.

This file defines periodic tasks for generating analytics reports.
"""

from celery.schedules import crontab

# Schedule reports to check every hour for due reports
CELERY_BEAT_SCHEDULE = {
    'check-analytics-reports': {
        'task': 'apps.analytics.tasks.check_and_send_due_reports',
        'schedule': crontab(minute=0),  # Every hour
    },
    'cleanup-old-reports': {
        'task': 'apps.analytics.tasks.cleanup_old_report_logs',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        'kwargs': {'days': 90}
    },
}

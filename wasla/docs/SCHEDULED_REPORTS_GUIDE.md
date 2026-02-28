# Scheduled Reports Feature Guide

## Overview

The Scheduled Reports feature enables automated generation and delivery of analytics reports to merchants and administrators. Reports can be scheduled at daily, weekly, or monthly intervals and delivered via email in multiple formats.

## Architecture

### Models

#### ScheduledReport
Defines a scheduled report configuration:

```python
class ScheduledReport(models.Model):
    # Scope
    store_id: int | None          # Merchant's store (None for admin)
    is_admin: bool                # Platform-wide report flag
    
    # Configuration
    report_type: str              # kpi_summary | revenue_analysis | conversion_funnel | executive_summary
    frequency: str                # daily | weekly | monthly
    delivery_format: str          # csv | html_email | json
    
    # Recipients
    email_recipients: JSONField   # List of email addresses
    
    # Scheduling
    is_active: bool               # Enable/disable report
    last_sent_at: datetime        # When report was last sent
    next_send_at: datetime        # When next report should send
    
    # Tracking
    created_at: datetime          # Creation timestamp
    updated_at: datetime          # Last update timestamp
```

**Indexes:**
- `(is_active, next_send_at)` - Fast lookup of due reports
- `(store_id, is_active)` - Filter by store

#### ReportLog
Tracks execution history of reports:

```python
class ReportLog(models.Model):
    scheduled_report: ScheduledReport  # Associated scheduled report
    status: str                        # pending | generated | sent | failed
    
    report_data: JSONField             # Report content (metrics, etc.)
    file_content: FileField            # Exported file (if applicable)
    
    generated_at: datetime             # When report was generated
    sent_at: datetime | None           # When report was sent
    error_message: str                 # Error details if failed
```

**Ordering:** `-generated_at` (newest first)

### Services

#### ReportService

The main service layer for report operations:

```python
class ReportService:
    @staticmethod
    def create_scheduled_report(
        report_type: str,
        frequency: str,
        email_recipients: list[str],
        store_id: int | None = None,
        is_admin: bool = False,
        delivery_format: str = 'html_email'
    ) -> ScheduledReport
```
Creates a new scheduled report with automatic next send time calculation.

```python
    @staticmethod
    def generate_merchant_report(scheduled_report: ScheduledReport) -> ReportLog
```
Generates a merchant report including:
- 8 merchant KPIs
- 30-day revenue chart data
- 7-day conversion funnel

```python
    @staticmethod
    def generate_admin_report(scheduled_report: ScheduledReport) -> ReportLog
```
Generates platform-wide executive report including:
- Platform KPIs (GMV, MRR, active stores, churn)
- Top 5 products and merchants

```python
    @staticmethod
    def send_report(report_log: ReportLog) -> bool
```
Sends report via email using Django's email backend. Returns success status.

```python
    @staticmethod
    def get_due_reports() -> list[ScheduledReport]
```
Gets all scheduled reports that are due to run (next_send_at <= now).

```python
    @staticmethod
    def export_report_csv(report_log: ReportLog) -> str
```
Exports report data as CSV format.

### Celery Integration

#### Tasks (`apps/analytics/tasks.py`)

```python
@shared_task
def check_and_send_due_reports()
```
Periodic task that checks for due reports and queues them for generation.

```python
@shared_task
def generate_and_send_report(report_id: int)
```
Generates and sends a single report asynchronously.

```python
@shared_task
def cleanup_old_report_logs(days: int = 90)
```
Deletes report logs older than specified days.

#### Schedule Configuration (`apps/analytics/celery_schedule.py`)

```python
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
```

## Report Types & Data

### 1. KPI Summary

**Merchant Report** - Daily key metrics snapshot

**Data Included:**
- Today's revenue
- Today's orders
- Conversion rate
- 7-day revenue
- 30-day revenue

**Use Case:** Quick daily digest of store performance

### 2. Revenue Analysis

**Merchant Report** - Detailed revenue trends

**Data Included:**
- 30-day total revenue
- Total orders count
- Daily breakdown points

**Use Case:** Track revenue trends over month

### 3. Conversion Funnel

**Merchant Report** - Customer journey analysis

**Data Included:**
- Product views
- Add to cart count
- Checkout started count
- Purchase completed count
- Conversion rates per stage

**Use Case:** Identify drop-off points in sales funnel

### 4. Executive Summary

**Admin Report** - Platform-wide performance metrics

**Data Included:**
- Gross Merchandise Value (GMV)
- Monthly Recurring Revenue (MRR)
- Active stores count
- Churn rate
- Total customers
- Platform conversion rate
- Top 5 products by revenue
- Top 5 merchants by revenue

**Use Case:** Executive dashboard digest for platform owners

## Email Templates

Reports are delivered via HTML email using Django template system.

**Template:** `templates/analytics/report_email.html`

**Features:**
- Responsive design (mobile & desktop)
- Color-coded metric cards
- Funnel visualization
- Data tables for top products/merchants
- Direct link to dashboard

## API Endpoints

### Management Commands

```bash
# Send only due reports (from Celery schedule)
python manage.py generate_analytics_reports

# Force send all active reports
python manage.py generate_analytics_reports --all

# Send specific report by ID
python manage.py generate_analytics_reports --id 42

# Send all reports for a store
python manage.py generate_analytics_reports --store-id 10
```

### REST API Endpoints

**Create Report**
```
POST /api/analytics/reports/
{
    "report_type": "kpi_summary",
    "frequency": "daily",
    "email_recipients": ["merchant@example.com"],
    "delivery_format": "html_email"
}
```

**List Reports**
```
GET /api/analytics/reports/
```

**Get Report Details**
```
GET /api/analytics/reports/{id}/
```

**Test Send Report**
```
POST /api/analytics/reports/{id}/test_send/
```

**Get Report Logs**
```
GET /api/analytics/reports/{id}/logs/
```

**Toggle Report Status**
```
POST /api/analytics/reports/{id}/toggle_active/
```

**Bulk Update**
```
POST /api/analytics/reports/bulk_update/
{
    "ids": [1, 2, 3],
    "is_active": true
}
```

## Admin Interface

Django admin provides full management of reports:

**URL:** `/admin/analytics/scheduledreport/`

**Features:**
- List view with filters (type, frequency, status, date)
- Search by store_id and email recipients
- Inline display of next_send_at and last_sent_at
- Quick actions: activate/deactivate
- View report logs from list view

**Report Logs Admin**
- Readonly view of all generated reports
- Filter by status (pending, generated, sent, failed)
- View JSON report data
- Display error messages for failed reports

## Deployment

### 1. Database Migrations

```bash
python manage.py makemigrations analytics
python manage.py migrate analytics
```

### 2. Celery Configuration

Add to `config/celery.py`:

```python
from apps.analytics.celery_schedule import CELERY_BEAT_SCHEDULE

# ... existing config ...

app.conf.beat_schedule = CELERY_BEAT_SCHEDULE
```

### 3. Email Configuration

Ensure Django email settings in `config/settings.py`:

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@example.com'
EMAIL_HOST_PASSWORD = 'your-password'
DEFAULT_FROM_EMAIL = 'noreply@wasla.io'
```

### 4. Start Celery Beat

```bash
celery -A config worker -l info
celery -A config beat -l info
```

### 5. Register Admin

Add to `apps/analytics/admin.py`:

```python
from apps.analytics.admin_reports import ScheduledReportAdmin, ReportLogAdmin
```

## Usage Examples

### Example 1: Create Daily KPI Report

**Via Management Command:**
```python
# Create programmatically
from apps.analytics.models_reports import ReportService

report = ReportService.create_scheduled_report(
    report_type='kpi_summary',
    frequency='daily',
    email_recipients=['admin@store.com'],
    store_id=1,
    delivery_format='html_email'
)
```

**Via Django Admin:**
1. Go to `/admin/analytics/scheduledreport/`
2. Click "Add Scheduled Report"
3. Select:
   - Report Type: KPI Summary
   - Frequency: Daily
   - Email Recipients: admin@store.com
4. Click Save

### Example 2: Test Send Report

```python
from apps.analytics.models_reports import ScheduledReport, ReportService

report = ScheduledReport.objects.get(id=42)
log = ReportService.generate_merchant_report(report)
ReportService.send_report(log)
```

### Example 3: View Report History

```python
from apps.analytics.models_reports import ReportLog

logs = ReportLog.objects.filter(
    scheduled_report_id=42,
    status='sent'
).order_by('-sent_at')[:10]

for log in logs:
    print(f"Sent on {log.sent_at}: {log.report_data}")
```

## Monitoring & Troubleshooting

### Check For Due Reports

```bash
python manage.py generate_analytics_reports
```

Output shows:
- Number of due reports
- Processing status for each
- Success/failure indicators

### View Failed Reports

```python
from apps.analytics.models_reports import ReportLog

failed = ReportLog.objects.filter(status='failed').order_by('-generated_at')
for log in failed:
    print(f"Report {log.id}: {log.error_message}")
```

### Common Issues

**Email Not Sending:**
- Check EMAIL_HOST and EMAIL_PORT in settings
- Verify EMAIL_HOST_USER and EMAIL_HOST_PASSWORD
- Check firewall/provider SMTP settings

**Celery Not Running:**
- Start worker: `celery -A config worker -l info`
- Start beat: `celery -A config beat -l info`
- Check logs for errors

**Reports Not Due:**
- Verify next_send_at is past current time
- Check is_active flag is True
- Ensure Celery Beat is running

## Performance Considerations

### Database Indexes

Reports queries use indexes for:
- `is_active` + `next_send_at` → Fast due report lookup
- `store_id` + `is_active` → Fast store filtering

### Caching

Report data (KPIs, charts) uses existing 5-10 min cache TTL, reducing database load.

### Cleanup

Automatic daily cleanup removes report logs older than 90 days to manage storage.

## Future Enhancements

- [ ] Custom report templates
- [ ] Report scheduling UI component
- [ ] Real-time report preview
- [ ] PDF export format
- [ ] Conditional alerts based on thresholds
- [ ] Multi-format delivery (SMS, Slack integration)
- [ ] Report analytics (open rates, clicks)

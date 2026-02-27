# Settlement Automation - Quick Start Guide

## Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

This will install:
- celery>=5.3.0
- redis>=4.5.0
- django-celery-beat>=2.5.0

### 2. Install and Start Redis
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis

# Or use Docker
docker run -d -p 6379:6379 --name redis redis:alpine
```

### 3. Apply Database Migrations
```bash
python manage.py migrate
```

This creates Celery Beat database tables for persistent schedules.

### 4. Environment Variables (Optional)
Add to your `.env` file:
```bash
# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## Running Celery

### Development Mode
Open 3 terminals:

**Terminal 1: Django Server**
```bash
python manage.py runserver
```

**Terminal 2: Celery Worker**
```bash
celery -A config worker -l info
```

**Terminal 3: Celery Beat (Scheduler)**
```bash
celery -A config beat -l info
```

### Production Mode
Use Supervisor or systemd to run Celery as a daemon. See [SETTLEMENT_AUTOMATION_GUIDE.md](SETTLEMENT_AUTOMATION_GUIDE.md) for details.

## Verify Installation

### 1. Test Celery Worker
```bash
# In Django shell
python manage.py shell

>>> from config.celery import debug_task
>>> result = debug_task.delay()
>>> result.ready()  # Should return True after a few seconds
>>> result.result   # Should show "Request: <Request ...>"
```

### 2. Check Scheduled Tasks
```bash
# View beat schedule
celery -A config inspect scheduled

# Or in Django shell
python manage.py shell

>>> from django_celery_beat.models import PeriodicTask
>>> PeriodicTask.objects.all()
```

### 3. Test Settlement Processing (Dry Run)
```bash
python manage.py process_settlements --dry-run
```

Expected output:
```
Settlement Processing (DRY RUN)
=================================
Store: Example Store (ID: 1)
  Eligible Orders: 25
  Gross Amount: $15,000.00
  Fees: $375.00
  Net Amount: $14,625.00
```

## Admin Monitoring

### Access Dashboard
Open your browser:
```
http://localhost:8000/admin/settlements/dashboard/
```

You'll see:
- Recent settlements
- Status breakdown
- Health metrics
- Unsettled orders

### Trigger Manual Settlement
```bash
# Via CLI
python manage.py process_settlements --store-id 123

# Via API (requires staff authentication)
curl -X POST http://localhost:8000/admin/settlements/trigger/ \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"store_id": 123, "auto_approve": false}'
```

### Generate Reconciliation Report
```bash
# Detailed report
python manage.py reconcile_settlements --detailed

# JSON format for automation
python manage.py reconcile_settlements --json > report.json
```

## Scheduled Tasks

The following tasks run automatically:

| Task | Schedule | Description |
|------|----------|-------------|
| Process Settlements | Daily 2:00 AM | Create settlement batches for orders >24h old |
| Generate Reports | Daily 3:00 AM | Daily settlement statistics |
| Reconciliation | Every hour | Detect payment/settlement discrepancies |
| Cleanup Logs | Weekly Sunday 1:00 AM | Remove old logs (>90 days) |

## Common Commands

### Process Settlements
```bash
# All stores
python manage.py process_settlements

# Specific store
python manage.py process_settlements --store-id 123

# Multiple stores
python manage.py process_settlements --store-ids 123,456,789

# Auto-approve settlements
python manage.py process_settlements --auto-approve

# Async (via Celery)
python manage.py process_settlements --async

# Preview only
python manage.py process_settlements --dry-run
```

### Reconciliation
```bash
# Last 7 days (default)
python manage.py reconcile_settlements

# Last 30 days
python manage.py reconcile_settlements --lookback-days 30

# Specific store
python manage.py reconcile_settlements --store-id 123

# Detailed output
python manage.py reconcile_settlements --detailed

# JSON output
python manage.py reconcile_settlements --json
```

### Check Task Status
```bash
# Check specific task
python manage.py check_task_status <task-id>

# Wait for completion (5 min timeout)
python manage.py check_task_status <task-id> --wait
```

## Monitoring Celery

### Worker Status
```bash
celery -A config inspect active
celery -A config inspect stats
celery -A config inspect scheduled
```

### Task History
```bash
celery -A config events
```

### Flower (Web-based Monitoring)
```bash
# Install
pip install flower

# Run
celery -A config flower --port=5555

# Access
http://localhost:5555
```

## Troubleshooting

### Redis Connection Failed
```bash
# Check Redis is running
redis-cli ping
# Should return: PONG

# Check Redis logs
sudo tail -f /var/log/redis/redis-server.log
```

### Worker Not Processing Tasks
```bash
# Check worker is running
ps aux | grep celery

# View worker logs
# (Check terminal where you started the worker)

# Restart worker
# Ctrl+C to stop, then restart:
celery -A config worker -l info
```

### Beat Not Scheduling Tasks
```bash
# Check beat is running
ps aux | grep "celery.*beat"

# Check database backend
python manage.py shell
>>> from django_celery_beat.models import PeriodicTask
>>> PeriodicTask.objects.filter(enabled=True)

# Restart beat
# Ctrl+C to stop, then restart:
celery -A config beat -l info
```

### No Eligible Orders
This is normal if:
- Orders are less than 24 hours old
- Orders are already settled
- No paid orders exist

Run with `--dry-run` to see details:
```bash
python manage.py process_settlements --dry-run
```

### Health Score Low
Check reconciliation report:
```bash
python manage.py reconcile_settlements --detailed
```

Look for:
- Unsettled paid orders (>24h old)
- Orphaned settlement items
- Amount mismatches
- Payment/settlement balance differences

## Next Steps

1. **Set up monitoring alerts** - Configure notifications for:
   - Health score < 60
   - Unsettled orders > threshold
   - Task failures

2. **Configure production deployment** - See [SETTLEMENT_AUTOMATION_GUIDE.md](SETTLEMENT_AUTOMATION_GUIDE.md) for Supervisor/systemd setup

3. **Run tests** - Validate settlement logic:
   ```bash
   pytest apps/settlements/
   ```

4. **Review logs** - Monitor settlement processing:
   ```bash
   tail -f /var/log/wasla/celery-worker.log
   ```

## Support

For detailed documentation, see:
- [SETTLEMENT_AUTOMATION_GUIDE.md](SETTLEMENT_AUTOMATION_GUIDE.md) - Complete guide
- [Settlement Models](../apps/settlements/models.py) - Data models
- [Settlement Tasks](../apps/settlements/tasks.py) - Background tasks
- [Reconciliation Service](../apps/settlements/application/reconciliation.py) - Reconciliation logic

For issues or questions, contact the development team.

# Settlement Automation System - Configuration & Monitoring Guide

**Status:** Production Ready  
**Activation Date:** 2026-02-25  
**Scheduler:** Celery Beat (Redis-backed)  
**Processing Frequency:** Hourly (every hour at :00)  

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Celery Configuration](#celery-configuration)
3. [Hourly Settlement Processing](#hourly-settlement-processing)
4. [Reconciliation Reports](#reconciliation-reports)
5. [Health Monitoring](#health-monitoring)
6. [Monitoring Logs](#monitoring-logs)
7. [Troubleshooting](#troubleshooting)
8. [Operations Guide](#operations-guide)

---

## System Overview

The settlement automation system processes pending orders every hour, respecting Wasla's 24-hour guarantee policy. It includes:

| Feature | Schedule | Purpose |
|---------|----------|---------|
| **Settlement Processing** | Every hour at :00 | Process eligible orders into settlements |
| **Reconciliation** | Every hour at :30 | Compare payments vs settlements |
| **Daily Reports** | 03:00 UTC | Generate summary of previous day |
| **Health Monitoring** | On-demand | Monitor system health metrics |
| **Cleanup** | Weekly (Sunday) | Archive old logs and records |

### Automation Policy: 24-Hour Hold

Orders eligible for settlement must be:
- **Payment Status:** `confirmed` (fully paid)
- **Age:** At least 24 hours old (cutoff: `now - 24h`)
- **Settlement Status:** Not already part of a settlement

This ensures customers have time to dispute or cancel before merchant settlement.

---

## Celery Configuration

### settings.py - Celery Settings

```python
# File: config/settings.py

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# Serialization
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# Timezone
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True

# Task configuration
CELERY_RESULT_EXPIRES = 3600  # Results expire after 1 hour
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
```

### celery.py - Beat Schedule Configuration

```python
# File: config/celery.py

app.conf.beat_schedule = {
    "process-pending-settlements-hourly": {
        "task": "apps.settlements.tasks.process_pending_settlements",
        "schedule": crontab(minute=0),  # Every hour at :00
        "kwargs": {"auto_approve": False},
        "options": {"queue": "settlements"},
    },
    "reconcile-payments-settlements-hourly": {
        "task": "apps.settlements.tasks.reconcile_payments_and_settlements",
        "schedule": crontab(minute=30),  # Every hour at :30
        "kwargs": {"lookback_days": 7},
        "options": {"queue": "settlements"},
    },
    "generate-settlement-reports-daily": {
        "task": "apps.settlements.tasks.generate_daily_settlement_reports",
        "schedule": crontab(hour=3, minute=0),  # 03:00 UTC
        "options": {"queue": "settlements"},
    },
    "cleanup-old-logs-weekly": {
        "task": "apps.settlements.tasks.cleanup_old_settlement_logs",
        "schedule": crontab(hour=1, minute=0, day_of_week=0),  # Sunday 01:00 UTC
        "kwargs": {"retention_days": 90},
        "options": {"queue": "settlements"},
    },
}
```

---

## Hourly Settlement Processing

### Task: `process_pending_settlements()`

**Schedule:** Every hour at :00  
**Queue:** settlements  
**Timeout:** 30 minutes  

### How It Works

```
[EVERY HOUR AT :00]
    ↓
1. Get all active stores
2. For each store:
   - Calculate cutoff: now - 24 hours
   - Find paid orders created before cutoff
   - Exclude already-settled orders
   - Create settlement batch
   - Update ledger balances (if approved)
3. Log batch summary
4. Return statistics
```

### Eligibility Criteria

Orders are processed if **ALL** conditions met:

```python
order.payment_status == "paid"
AND order.created_at < (now - 24 hours)
AND order NOT IN SettlementItem
```

### Example

**Time: 2026-02-25 14:00 UTC**

```
Cutoff time: 2026-02-24 14:00 UTC

Processing:
✅ Order #1001: paid at 14:33 Feb 23 → INCLUDED (33h old)
✅ Order #1002: paid at 12:15 Feb 23 → INCLUDED (25h old)
❌ Order #1003: paid at 15:00 Feb 24 → SKIPPED (23h old)
❌ Order #1004: paid at 10:00 Feb 23 → SKIPPED (already settled)
```

### Sample Output

```python
{
    "total_stores": 5,
    "settlements_created": 3,
    "settlements_approved": 0,
    "total_orders_processed": 27,
    "total_amount_settled": Decimal("15234.50"),
    "errors": [],
}
```

### Batch Summary Log Output

```
╔═══════════════════════════════════════════════════════════════╗
║ SETTLEMENT BATCH SUMMARY                                      ║
╠═══════════════════════════════════════════════════════════════╣
║ Stores Processed:                            5                ║
║ Settlements Created:                         3                ║
║ Settlements Approved:                        0                ║
║ Orders Processed:                           27                ║
║ Total Amount Settled:                $15234.50                ║
║ Errors:                                      0                ║
╚═══════════════════════════════════════════════════════════════╝
```

---

## Reconciliation Reports

### Task: `reconcile_payments_and_settlements()`

**Schedule:** Every hour at :30  
**Lookback Period:** 7 days (configurable)  
**Reports:** Discrepancies between payment intents and settlements  

### What It Checks

#### 1. Unsettled Paid Orders (Beyond Grace Period)
```
Orders where:
- payment_status = "paid"
- created_at < (now - 24 hours)
- NOT in SettlementItem

Indicates: Orders that should have been settled but haven't
```

#### 2. Orphaned Settlement Items
```
Settlement items where:
- order.payment_status != "paid"

Indicates: Settlement items without corresponding paid orders
```

#### 3. Amount Mismatches
```
Items where:
- settlement_item.order_amount != order.total_amount

Indicates: Amount discrepancies in settlement
```

#### 4. Payment vs Settlement Totals
```
Compares:
- Sum of all PaymentIntent amounts (paid)
- Sum of all SettlementItem amounts

Indicates: Overall variance in the system
```

### Sample Reconciliation Report

```python
{
    "period": {
        "lookback_days": 7,
        "from": "2026-02-18T14:30:00Z",
        "to": "2026-02-25T14:30:00Z",
        "grace_period_hours": 24,
    },
    "payment_intents": {
        "count": 142,
        "total": "45678.50",
    },
    "settlement_items": {
        "count": 142,
        "total": "45678.50",
    },
    "variance": {
        "amount": "0.00",
        "percentage": "0.00",
        "status": "OK",
    },
    "unsettled_paid_orders": {
        "count": 0,
        "total": "0.00",
        "note": "Beyond 24h grace period, should be settled",
    },
    "orphaned_items": {
        "count": 0,
        "total": "0.00",
        "status": "OK",
    },
    "amount_mismatches": {
        "count": 0,
        "status": "OK",
        "sample": [],
    },
    "generated_at": "2026-02-25T14:30:45Z",
}
```

### Alert Conditions

| Condition | Severity | Action |
|-----------|----------|--------|
| Unsettled orders > 0 | ⚠️ Warning | Check payment processing |
| Orphaned items > 0 | ⚠️ Warning | Investigate settlement integrity |
| Amount mismatches > 0 | ⚠️ Warning | Review affected orders |
| Variance > $1.00 | 🔴 Critical | Halt settlements, investigate |

---

## Health Monitoring

### Task: `monitor_settlement_health()`

**Frequency:** On-demand (can be called manually or scheduled)  
**Metrics:** System health indicators  

### Collected Metrics

```python
{
    "settlement_volume_24h": {
        "count": <number of settlements created>,
        "total_gross": <sum of gross amounts>,
        "total_net": <sum of net amounts>,
        "breakdown": {
            "created": <count>,
            "approved": <count>,
            "paid": <count>,
            "failed": <count>,
        },
    },
    "pending_items": {
        "pending_settlements": <count of unpaid settlements>,
        "unsettled_paid_orders": <count of orders waiting settlement>,
    },
    "system_health": {
        "ledger_accounts_negative": <count of negative balances>,
        "settlement_velocity_per_day": <average settlements/day>,
    },
    "status": "healthy" | "warning",
}
```

### Health Status Determination

```
Status = "healthy" if:
  - ledger_accounts_negative == 0
  - unsettled_paid_orders < 100

Status = "warning" if:
  - ledger_accounts_negative > 0
  - unsettled_paid_orders >= 100
```

### Manual Monitoring

```bash
# Run health check manually
python manage.py shell

from apps.settlements.tasks import monitor_settlement_health
result = monitor_settlement_health.apply_sync()
print(result)
```

---

## Monitoring Logs

### Log Levels

| Level | When Used | Example |
|-------|-----------|---------|
| **INFO** | Normal operations | "Starting process_pending_settlements" |
| **WARNING** | Discrepancies found | "Found 5 unsettled paid orders" |
| **ERROR** | Task failures | "Error processing settlement for store 5" |
| **EXCEPTION** | Fatal errors | Retry and escalate |

### Log Location

```
# All settlement logs go to:
/var/log/django/settlements.log

# Or via Django logger:
logger = logging.getLogger("apps.settlements.tasks")
```

### Sample Log Output

```
2026-02-25 14:00:00 INFO Starting process_pending_settlements task
2026-02-25 14:00:01 INFO Created settlement 142 for store 5: 8 orders, 1200.00 gross
2026-02-25 14:00:02 INFO Created settlement 143 for store 12: 5 orders, 750.00 gross
2026-02-25 14:00:03 INFO Completed process_pending_settlements: {
    "total_stores": 27,
    "settlements_created": 3,
    "settlements_approved": 0,
    "total_orders_processed": 13,
    "total_amount_settled": "1950.00",
    "errors": []
}

╔═══════════════════════════════════════════════════════════════╗
║ SETTLEMENT BATCH SUMMARY                                      ║
╠═══════════════════════════════════════════════════════════════╣
║ Stores Processed:                           27                ║
║ Settlements Created:                         3                ║
║ Settlements Approved:                        0                ║
║ Orders Processed:                           13                ║
║ Total Amount Settled:              $1950.00                   ║
║ Errors:                                      0                ║
╚═══════════════════════════════════════════════════════════════╝

2026-02-25 14:30:00 INFO Starting reconciliation for last 7 days
2026-02-25 14:30:05 INFO Reconciliation completed: {
    "period": {...},
    "payment_intents": {"count": 142, "total": "45678.50"},
    "settlement_items": {"count": 142, "total": "45678.50"},
    "variance": {"amount": "0.00", "percentage": "0.00", "status": "OK"},
    ...
}
```

### Monitoring Integration

```bash
# Watch logs in real-time
tail -f /var/log/django/settlements.log

# Filter for errors
grep ERROR /var/log/django/settlements.log

# Filter for warnings
grep WARNING /var/log/django/settlements.log

# Search for specific store
grep "store 5" /var/log/django/settlements.log
```

---

## Troubleshooting

### Issue: Tasks Not Running

**Symptoms:** No settlements created, no log entries

**Diagnosis:**

```bash
# Check if Celery Beat is running
ps aux | grep celery

# Check if Redis is running
redis-cli ping
# Should return: PONG

# Check task queue
celery -A config inspect active_queues
```

**Solution:**

```bash
# Start Celery Beat (if not running)
celery -A config beat -l info

# In another terminal, start worker
celery -A config worker -Q settlements -l info
```

### Issue: Stuck Tasks

**Symptoms:** Tasks show as "started" but never complete

**Diagnosis:**

```bash
# List active tasks
celery -A config inspect active

# Check for long-running tasks
celery -A config inspect stats | grep time_limit
```

**Solution:**

```bash
# Revoke stuck task (replace TASK_ID)
celery -A config revoke TASK_ID --terminate

# Clear queue if corrupted
celery -A config purge
# WARNING: This deletes all pending tasks
```

### Issue: Reconciliation Shows Mismatches

**Symptoms:** Variance > 0, orphaned items detected

**Diagnosis:**

```python
# Check unsettled orders
from apps.orders.models import Order
from apps.settlements.models import SettlementItem
from django.db.models import Exists, OuterRef

already_settled = SettlementItem.objects.filter(order_id=OuterRef("pk"))
unsettled = Order.objects.filter(
    payment_status="paid",
).annotate(is_settled=Exists(already_settled)).filter(
    is_settled=False
)

print(f"Unsettled orders: {unsettled.count()}")
print(f"Total amount: {unsettled.aggregate(Sum('total_amount'))}")

# Check for orphaned items
from apps.settlements.models import SettlementItem
orphaned = SettlementItem.objects.exclude(order__payment_status="paid")
print(f"Orphaned items: {orphaned.count()}")
```

**Solution:**

```python
# Manually settle missing orders
from apps.settlements.tasks import process_pending_settlements
result = process_pending_settlements.apply_async(
    kwargs={"auto_approve": True}
)

# Or trigger full processing
from apps.settlements.tasks import process_pending_settlements
result = process_pending_settlements.apply_async()
```

### Issue: Celery Tasks Timing Out

**Symptoms:** Task time limit exceeded, settlements incomplete

**Diagnosis:**

```bash
# Check task timeout settings
python manage.py shell
>>> from django.conf import settings
>>> print(settings.CELERY_TASK_TIME_LIMIT)
>>> print(settings.CELERY_TASK_SOFT_TIME_LIMIT)
```

**Solution:**

```python
# In config/settings.py, increase limits if necessary
CELERY_TASK_TIME_LIMIT = 45 * 60  # 45 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 40 * 60  # 40 minutes
```

---

## Operations Guide

### Starting the System

```bash
# Terminal 1: Start Celery Beat scheduler
celery -A config beat -l info

# Terminal 2: Start Celery worker
celery -A config worker -Q settlements -l info

# Verify tasks are registered
celery -A config inspect registered
```

### Monitoring Production

```bash
# Monitor settlement processing
watch -n 60 'tail -20 /var/log/django/settlements.log'

# Check task queue depth
celery -A config inspect active_queues

# Monitor Redis
redis-cli LLEN celery

# Get task statistics
celery -A config inspect stats
```

### Manual Task Triggering

```python
# In Django shell
python manage.py shell

from apps.settlements.tasks import (
    process_pending_settlements,
    reconcile_payments_and_settlements,
    monitor_settlement_health,
    generate_reconciliation_report,
)

# Process settlements manually
result = process_pending_settlements.apply_async()
print(f"Task ID: {result.id}")

# Check specific stores
result = process_pending_settlements.apply_async(
    kwargs={"store_ids": [5, 12, 23]}
)

# Get results
print(result.get(timeout=30))
```

### Testing

```bash
# Run settlement automation tests
python manage.py test apps.settlements.tests_automation

# Run specific test class
python manage.py test apps.settlements.tests_automation.ProcessPendingSettlementsTests

# Run with verbose output
python manage.py test apps.settlements -v 2
```

### Performance Tuning

```python
# In config/settings.py

# Increase worker concurrency
CELERY_WORKER_PREFETCH_MULTIPLIER = 4  # Default
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000  # Default

# Reduce result expiration if disk space is tight
CELERY_RESULT_EXPIRES = 1800  # 30 minutes (default 3600)

# Enable compression for large payloads
CELERY_TASK_COMPRESSION = "gzip"
```

### Alerts to Configure

```python
# Monitor these metrics in your APM/monitoring system:

1. Settlement processing latency (should be < 5 minutes)
2. Reconciliation variance (should be 0.00)
3. Orphaned items count (should be 0)
4. Unsettled orders after grace period (should be < 10)
5. Ledger account negative balances (should be 0)
6. Task failure rate (should be < 0.1%)
7. Queue depth (should process within hour)
```

---

## Advanced Configuration

### Custom Hourly Offsets

To run settlements at specific minutes each hour:

```python
# In config/celery.py

app.conf.beat_schedule = {
    "process-pending-settlements-hourly": {
        "task": "apps.settlements.tasks.process_pending_settlements",
        "schedule": crontab(minute='*/10'),  # Every 10 minutes
        "kwargs": {"auto_approve": False},
    },
}
```

### Per-Store Processing

To process specific stores only:

```python
# One-time processing
from apps.settlements.tasks import process_pending_settlements

result = process_pending_settlements.apply_async(
    kwargs={
        "store_ids": [5, 12, 23],  # Only these stores
        "auto_approve": False,
    }
)
```

### Auto-Approval

To automatically approve settlements (use with caution):

```python
# In config/celery.py
"kwargs": {"auto_approve": True},  # Approve all created settlements

# Or manually
from apps.settlements.tasks import process_pending_settlements
result = process_pending_settlements.apply_async(
    kwargs={"auto_approve": True}
)
```

---

## Conclusion

The settlement automation system ensures:

✅ **Fair Processing:** 24-hour hold before settlement  
✅ **Accurate Tracking:** Complete reconciliation every hour  
✅ **System Health:** Continuous monitoring and alerts  
✅ **Transparency:** Detailed logging at every step  
✅ **Reliability:** Automatic retries and error handling  

For issues, check logs and run health monitoring. Escalate if variance detected.

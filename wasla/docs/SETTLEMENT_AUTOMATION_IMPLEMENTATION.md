# SETTLEMENT AUTOMATION IMPLEMENTATION GUIDE

Enterprise-grade settlement automation system for Wasla multi-tenant SaaS platform.

**Implementation Date:** February 25, 2026  
**Status:** Complete  
**Scope:** Idempotent batch processing, 24h SLA enforcement, reconciliation, monitoring

## A. IMPLEMENTATION STATUS

✅ **Models & Database**
- `SettlementBatch` (idempotent batch tracking)
- `SettlementBatchItem` (per-order batch tracking)
- `SettlementRunLog` (task audit trail)
- `ReconciliationReport` (payment vs settlement discrepancies)
- Migration: `0007_settlement_automation.py`

✅ **Services Layer**
- `SettlementAutomationService` (batch creation & processing)
- `ReconciliationService` (discrepancy detection)
- File: `apps/settlements/services/settlement_automation_service.py`

✅ **Celery Automation Tasks**
- `automation_process_pending_settlements` (hourly)
- `automation_run_reconciliation` (daily)
- `automation_monitor_settlement_health` (hourly)
- `automation_cleanup_old_batches` (weekly)
- File: `apps/settlements/tasks_automation.py`

✅ **API Endpoints (DRF)**
- Merchant: `GET /api/settlements/batches/`, detail, summary
- Admin: `GET /api/admin/settlements/batches/`, stats, manual trigger
- Admin: Reconciliation reports view
- Admin: Health monitoring & logs
- File: `apps/settlements/views_automation.py`

✅ **Serializers**
- `SettlementBatchSerializer`
- `ReconciliationReportSerializer`
- `SettlementRunLogSerializer`
- File: `apps/settlements/serializers_automation.py`

✅ **Celery Beat Schedule**
- Extended with 4 new automation tasks
- Config: `config/celery.py`

✅ **Settings Configuration**
- `SETTLEMENT_DELAY_HOURS` (24)
- `SETTLEMENT_BATCH_SIZE` (100)
- `SETTLEMENT_AUTO_APPROVE` (False)
- `SETTLEMENT_RECONCILIATION_LOOKBACK_DAYS` (7)
- File: `config/settings.py`

## B. QUICK START

### 1. Apply Database Migration
```bash
python manage.py migrate settlements
```

### 2. Start Services
```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Celery Worker
celery -A config worker -l info -Q settlements,default

# Terminal 3: Celery Beat
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### 3. Verify Setup
```bash
python manage.py shell
>>> from apps.settlements.models import SettlementBatch
>>> SettlementBatch.objects.count()
0
```

### 4. Trigger Manual Settlement (Admin API)
```bash
curl -X POST http://localhost:8000/api/admin/settlements/batches/run_manual/ \
  -H "Content-Type: application/json" \
  -d '{"store_ids": [1]}'
```

## C. KEY FEATURES

### Idempotency
- Unique `idempotency_key` per batch based on order IDs
- Same input = same batch (no duplicates on retry)
- Safe for distributed execution

### 24-Hour SLA Policy
- Only settles orders > 24h old
- Prevents premature settlement
- Configurable: `SETTLEMENT_DELAY_HOURS`

### Atomic Transactions
- All operations wrapped in `@transaction.atomic`
- Consistent database state
- Recoverable on failure

### Comprehensive Logging
- `SettlementRunLog`: Every task execution
- `SettlementBatch`: Per-batch tracking
- Task ID tracking for debugging

### Reconciliation Engine
- Compares expected vs settled amounts
- Detects unsettled orders beyond grace
- Identifies discrepancies with root cause

### Health Monitoring
- System status: healthy/warning/error
- Alerts on stale batches, failures, errors
- Extensible to send notifications

## D. MODELS

### SettlementBatch
```python
- store: ForeignKey(Store)
- batch_reference: str (unique with store)
- idempotency_key: str (unique)
- total_orders, total_amount, total_fees, total_net: Decimal
- status: processing, completed, failed, partial
- orders_succeeded, orders_failed: int
- duration_ms: int
```

### SettlementBatchItem
```python
- batch: ForeignKey(SettlementBatch)
- order: ForeignKey(Order)
- order_amount, calculated_fee, calculated_net: Decimal
- status: included, processed, failed, skipped
```

### ReconciliationReport
```python
- store: ForeignKey(Store)
- period_start, period_end: Date
- expected_total, settled_total, discrepancy: Decimal
- unsettled_orders_count, orphaned_items_count: int
- status: ok, warning, error
- findings: JSON array
```

### SettlementRunLog
```python
- task_name: str
- task_id: str (Celery ID)
- status: started, completed, failed
- orders_processed, batches_created: int
- duration_ms: int
```

## E. TASKS

### automation_process_pending_settlements
Runs: Every hour at :15  
Arguments: `store_ids` (optional)  
Returns:
```python
{
    "task_id": "...",
    "stores_processed": 5,
    "batches_created": 7,
    "orders_processed": 350,
    "total_amount": "5000.00",
    "errors": []
}
```

### automation_run_reconciliation
Runs: Daily at 02:00 UTC  
Arguments: `store_ids` (optional)  
Returns:
```python
{
    "stores_reconciled": 5,
    "reports_created": 5,
    "discrepancies_found": 2
}
```

### automation_monitor_settlement_health
Runs: Every hour at :45  
Returns:
```python
{
    "status": "healthy|warning|error",
    "batches_24h": {...},
    "stale_batches": 0,
    "recent_errors": 0,
    "alerts": []
}
```

### automation_cleanup_old_batches
Runs: Weekly (Monday 00:00)  
Arguments: `retention_days` (default: 90)  
Returns:
```python
{
    "batches_deleted": 150,
    "logs_deleted": 4500,
    "cutoff_date": "2025-11-26"
}
```

## F. API ENDPOINTS

### Merchant APIs

**List Batches**
```
GET /api/settlements/batches/
?status=completed&created_at__gte=2026-01-01
```

**Batch Detail**
```
GET /api/settlements/batches/1/
```

**Batch Summary**
```
GET /api/settlements/batches/1/summary/
```

### Admin APIs

**Batches List**
```
GET /api/admin/settlements/batches/
?store=1&status=completed
```

**Batches Stats**
```
GET /api/admin/settlements/batches/stats/
```

**Trigger Manual Settlement**
```
POST /api/admin/settlements/batches/run_manual/
{"store_ids": [1, 2]}
→ {"task_id": "...", "status": "processing"}
```

**Reconciliation Reports**
```
GET /api/admin/settlements/reconciliation/
?status=error
```

**Reconciliation Summary**
```
GET /api/admin/settlements/reconciliation/summary/
```

**Trigger Manual Reconciliation**
```
POST /api/admin/settlements/reconciliation/run_manual/
{"store_ids": [1]}
→ {"task_id": "...", "status": "processing"}
```

**Health Monitor**
```
GET /api/admin/settlements/health/monitor/
```

**Run Logs**
```
GET /api/admin/settlements/health/logs/
?task_name=automation_process_pending_settlements&status=completed&limit=10
```

## G. SETTINGS

```python
# config/settings.py

# Hours before order is eligible for settlement
SETTLEMENT_DELAY_HOURS = 24

# Orders per batch
SETTLEMENT_BATCH_SIZE = 100

# Max orders per settlement run
SETTLEMENT_BATCH_MAX_ORDERS = 1000

# Settlement processing timeout (minutes)
SETTLEMENT_BATCH_TIMEOUT_MINUTES = 30

# Auto-approve settlements (default: False = manual approval)
SETTLEMENT_AUTO_APPROVE = False

# Reconciliation lookback (days)
SETTLEMENT_RECONCILIATION_LOOKBACK_DAYS = 7

# Audit log retention (days)
SETTLEMENT_AUDIT_LOG_RETENTION_DAYS = 90

# Enable detailed logging
SETTLEMENT_DETAILED_LOGGING = True

# Notification emails for alerts (comma-separated)
SETTLEMENT_NOTIFICATION_EMAILS = []

# Enable settlement processing
SETTLEMENT_PROCESSING_ENABLED = True
```

## H. FILES CREATED/MODIFIED

### New Files
- `apps/settlements/services/settlement_automation_service.py` (500+ lines)
- `apps/settlements/tasks_automation.py` (300+ lines)
- `apps/settlements/serializers_automation.py` (150+ lines)
- `apps/settlements/views_automation.py` (300+ lines)
- `apps/settlements/migrations/0007_settlement_automation.py`
- `docs/SETTLEMENT_AUTOMATION_GUIDE.md`

### Modified Files
- `config/settings.py` (added settlement config)
- `config/celery.py` (added automation tasks to beat schedule)
- `apps/settlements/models.py` (added 4 new models)

## I. CELERY SCHEDULE

| Task | Schedule | Queue |
|------|----------|-------|
| automation_process_pending_settlements | Every hour :15 | settlements |
| automation_run_reconciliation | Daily 02:00 UTC | settlements |
| automation_monitor_settlement_health | Every hour :45 | settlements |
| automation_cleanup_old_batches | Monday 00:00 UTC | settlements |

## J. DEPLOYMENT

### Prerequisites
- Python 3.8+
- Django 3.2+
- PostgreSQL (for idempotency)
- Redis (for Celery broker)

### Steps
1. Apply migration: `python manage.py migrate settlements`
2. Update `urls.py` with viewsets
3. Start Redis: `redis-server`
4. Start Worker: `celery -A config worker -Q settlements,default`
5. Start Beat: `celery -A config beat --scheduler django_celery_beat.schedulers:DatabaseScheduler`
6. Verify: Check Admin > Settlement Batches

### Environment Variables
```bash
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
SETTLEMENT_DELAY_HOURS=24
SETTLEMENT_BATCH_SIZE=100
SETTLEMENT_AUTO_APPROVE=0
```

## K. MONITORING

### Admin Interface
- Dashboard: View recent batches, reconciliation status
- Settlement Batches: Filter by status, store, date
- Settlement Run Logs: View task execution history
- Reconciliation Reports: Track discrepancies

### Celery Flower (Optional)
```bash
pip install flower
celery -A config flower --port=5555
# Access: http://localhost:5555
```

### Logs
```bash
tail -f logs/django.log | grep settlement
```

## L. TROUBLESHOOTING

| Issue | Solution |
|-------|----------|
| No batches created | Check if orders > 24h old exist |
| Worker not processing | Verify Redis connection, restart worker |
| Duplicate batches | Check idempotency_key uniqueness |
| Stale batches | Mark stuck status as FAILED, restart task |
| Discrepancies | Run reconciliation, check refund logic |

## M. FUTURE ENHANCEMENTS

- [ ] Merchant dashboard UI for batch tracking
- [ ] Admin portal dashboard for settlement monitoring
- [ ] Email notifications on batch completion/failure
- [ ] Webhook callbacks for payment integrations
- [ ] Exportable settlement reports (CSV/PDF)
- [ ] Batch retry mechanism with manual overrides
- [ ] Settlement reversal/adjustment support
- [ ] Multi-currency support

---

**Ready for production! Start Celery Beat and let the automation run.**

"""
Enterprise-grade settlement automation tasks extension.

These tasks provide:
- Idempotent batch processing
- 24-hour SLA enforcement
- Comprehensive reconciliation
- System health monitoring
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from celery import shared_task
from django.db import transaction
from django.db.models import Count, Q, Sum, Exists, OuterRef
from django.utils import timezone

from apps.settlements.models import SettlementBatch, ReconciliationReport, SettlementRunLog
from apps.settlements.services.settlement_automation_service import (
    SettlementAutomationService,
    ReconciliationService,
)
from apps.stores.models import Store

logger = logging.getLogger(__name__)


# ==============================================================================
# SETTLEMENT AUTOMATION TASKS (Enterprise-Grade)
# ==============================================================================

@shared_task(
    name="apps.settlements.tasks.automation_process_pending_settlements",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def automation_process_pending_settlements(self, store_ids: List[int] = None) -> Dict:
    """
    Process pending settlements using idempotent batch automation.
    
    Orchestrates:
    1. Find eligible orders (24h SLA policy enforcement)
    2. Create idempotent batches
    3. Log all activity
    4. Update ledger accounts
    
    Args:
        store_ids: Optional list of store IDs to process
    
    Returns:
        Dict with automation results
    """
    started_at = timezone.now()
    task_id = self.request.id
    service = SettlementAutomationService()
    
    try:
        logger.info("Starting automation_process_pending_settlements")
        
        # Get stores to process
        stores_qs = Store.objects.filter(status="active")
        if store_ids:
            stores_qs = stores_qs.filter(id__in=store_ids)
        
        stores = list(stores_qs.values_list("id", flat=True))
        logger.info(f"Processing {len(stores)} stores")
        
        results = {
            "task_id": task_id,
            "stores_processed": 0,
            "batches_created": 0,
            "orders_processed": 0,
            "total_amount": Decimal("0"),
            "errors": [],
        }
        
        cutoff_time = timezone.now() - timedelta(
            hours=service.settlement_delay_hours
        )
        
        for store_id in stores:
            try:
                store_result = service.process_store_settlements(
                    store_id=store_id,
                    cutoff_time=cutoff_time,
                )
                
                if store_result["success"]:
                    results["stores_processed"] += 1
                    results["batches_created"] += store_result.get(
                        "batches_created", 0
                    )
                    results["orders_processed"] += store_result.get(
                        "orders_processed", 0
                    )
                    
                    amount = Decimal(store_result.get("total_amount", "0"))
                    results["total_amount"] += amount
                else:
                    results["errors"].append(
                        {
                            "store_id": store_id,
                            "reason": store_result.get("reason", "Unknown"),
                        }
                    )
                    logger.warning(
                        f"Store {store_id} settlement failed: "
                        f"{store_result.get('reason')}"
                    )
            
            except Exception as e:
                logger.exception(f"Error processing store {store_id}: {e}")
                results["errors"].append(
                    {
                        "store_id": store_id,
                        "reason": str(e),
                    }
                )
        
        # Log the run
        completed_at = timezone.now()
        service.log_settlement_run(
            task_name="automation_process_pending_settlements",
            task_id=task_id,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            message=f"Processed {results['stores_processed']} stores, "
                    f"created {results['batches_created']} batches, "
                    f"settled ${results['total_amount']}",
            payload=results,
            orders_processed=results["orders_processed"],
            batches_created=results["batches_created"],
            total_amount=results["total_amount"],
        )
        
        logger.info(f"automation_process_pending_settlements completed: {results}")
        return results
    
    except Exception as exc:
        logger.exception("Fatal error in automation_process_pending_settlements")
        service.log_settlement_run(
            task_name="automation_process_pending_settlements",
            task_id=task_id,
            status="failed",
            started_at=started_at,
            completed_at=timezone.now(),
            message=f"Task failed: {str(exc)}",
            error_trace=str(exc),
        )
        raise self.retry(exc=exc)


@shared_task(
    name="apps.settlements.tasks.automation_run_reconciliation",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def automation_run_reconciliation(self, store_ids: List[int] = None) -> Dict:
    """
    Run comprehensive reconciliation comparing payments vs settlements.
    
    Generates:
    - ReconciliationReport per store
    - Detects discrepancies
    - Logs findings
    
    Args:
        store_ids: Optional store IDs to reconcile
    
    Returns:
        Dict with reconciliation results
    """
    started_at = timezone.now()
    task_id = self.request.id
    service = ReconciliationService()
    
    try:
        logger.info("Starting automation_run_reconciliation")
        
        # Get stores
        stores_qs = Store.objects.all()
        if store_ids:
            stores_qs = stores_qs.filter(id__in=store_ids)
        
        stores = list(stores_qs.values_list("id", flat=True))
        logger.info(f"Reconciling {len(stores)} stores")
        
        results = service.run_reconciliation()
        results["task_id"] = task_id
        
        # Log the run
        service_for_logging = SettlementAutomationService()
        service_for_logging.log_settlement_run(
            task_name="automation_run_reconciliation",
            task_id=task_id,
            status="completed",
            started_at=started_at,
            completed_at=timezone.now(),
            message=f"Reconciled {results['stores_reconciled']} stores, "
                    f"found {results['discrepancies_found']} discrepancies",
            payload=results,
        )
        
        logger.info(f"automation_run_reconciliation completed: {results}")
        return results
    
    except Exception as exc:
        logger.exception("Error in automation_run_reconciliation")
        raise self.retry(exc=exc)


@shared_task(
    name="apps.settlements.tasks.automation_monitor_settlement_health",
    bind=True,
)
def automation_monitor_settlement_health(self) -> Dict:
    """
    Monitor settlement system health and send alerts if needed.
    
    Checks:
    - Pending batches still processing
    - Failed batches
    - Recent discrepancies
    - System backlog
    
    Returns:
        Dict with health metrics
    """
    try:
        now = timezone.now()
        one_day_ago = now - timedelta(days=1)
        seven_days_ago = now - timedelta(days=7)
        
        # Batch health
        batches_24h = SettlementBatch.objects.filter(
            created_at__gte=one_day_ago
        ).aggregate(
            count=Count("id"),
            total_amount=Sum("total_amount"),
            processing=Count("id", filter=Q(status=SettlementBatch.STATUS_PROCESSING)),
            completed=Count("id", filter=Q(status=SettlementBatch.STATUS_COMPLETED)),
            failed=Count("id", filter=Q(status=SettlementBatch.STATUS_FAILED)),
            partial=Count("id", filter=Q(status=SettlementBatch.STATUS_PARTIAL)),
        )
        
        # Stale batches (processing > 1 hour)
        stale_batches = SettlementBatch.objects.filter(
            status=SettlementBatch.STATUS_PROCESSING,
            started_at__lt=now - timedelta(hours=1),
        ).count()
        
        # Reconciliation health
        recent_errors = ReconciliationReport.objects.filter(
            created_at__gte=seven_days_ago,
            status=ReconciliationReport.STATUS_ERROR,
        ).count()
        
        # System health status
        health_status = "healthy"
        alerts = []
        
        if stale_batches > 0:
            health_status = "warning"
            alerts.append(
                f"WARNING: {stale_batches} batches stale (processing > 1h)"
            )
        
        if (batches_24h["failed"] or 0) > 0:
            health_status = "warning"
            alerts.append(f"WARNING: {batches_24h['failed']} failed batches in 24h")
        
        if recent_errors > 0:
            health_status = "error"
            alerts.append(f"ERROR: {recent_errors} reconciliation errors in 7d")
        
        health_report = {
            "timestamp": now.isoformat(),
            "status": health_status,
            "batches_24h": {
                "count": batches_24h["count"] or 0,
                "total_amount": str(batches_24h["total_amount"] or Decimal("0")),
                "processing": batches_24h["processing"] or 0,
                "completed": batches_24h["completed"] or 0,
                "failed": batches_24h["failed"] or 0,
                "partial": batches_24h["partial"] or 0,
            },
            "stale_batches": stale_batches,
            "recent_errors": recent_errors,
            "alerts": alerts,
        }
        
        # Log
        if health_status == "healthy":
            logger.info(f"Settlement health: HEALTHY")
        else:
            log_level = logging.ERROR if health_status == "error" else logging.WARNING
            logger.log(
                log_level,
                f"Settlement health: {health_status.upper()} - {alerts}",
            )
        
        return health_report
    
    except Exception as exc:
        logger.exception("Error monitoring settlement health")
        raise


@shared_task(
    name="apps.settlements.tasks.automation_cleanup_old_batches",
    bind=True,
)
def automation_cleanup_old_batches(self, retention_days: int = 90) -> Dict:
    """
    Clean up old settlement batches and logs.
    
    Args:
        retention_days: Number of days to retain batch data
    
    Returns:
        Dict with cleanup results
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        # Delete old completed/failed batches
        deleted_batches = SettlementBatch.objects.filter(
            completed_at__lt=cutoff_date,
            status__in=[
                SettlementBatch.STATUS_COMPLETED,
                SettlementBatch.STATUS_FAILED,
            ],
        ).delete()
        
        # Delete old run logs
        deleted_logs = SettlementRunLog.objects.filter(
            created_at__lt=cutoff_date,
        ).delete()
        
        result = {
            "cleaned_at": timezone.now().isoformat(),
            "batches_deleted": deleted_batches[0] if deleted_batches else 0,
            "logs_deleted": deleted_logs[0] if deleted_logs else 0,
            "cutoff_date": cutoff_date.isoformat(),
        }
        
        logger.info(f"Cleanup completed: {result}")
        return result
    
    except Exception as exc:
        logger.exception("Error in cleanup task")
        raise

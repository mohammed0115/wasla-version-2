"""
Celery tasks for settlement processing.

This module contains background tasks for:
- Processing pending settlements (24h policy enforcement)
- Generating settlement reports
- Reconciliation between payments and settlements
- Administrative monitoring and cleanup
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List

from celery import shared_task
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.orders.models import Order
from apps.payments.models import PaymentIntent
from apps.settlements.application.use_cases.create_settlement import (
    CreateSettlementCommand,
    CreateSettlementUseCase,
)
from apps.settlements.application.use_cases.approve_settlement import (
    ApproveSettlementCommand,
    ApproveSettlementUseCase,
)
from apps.settlements.models import (
    LedgerAccount,
    Settlement,
    SettlementItem,
    SettlementRecord,
)
from apps.stores.models import Store

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.settlements.tasks.process_pending_settlements",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def process_pending_settlements(self, auto_approve: bool = False, store_ids: List[int] = None) -> Dict:
    """
    Process pending settlements for all stores or specific stores.
    
    Respects 24h policy: Only processes orders that are at least 24 hours old.
    
    Args:
        auto_approve: If True, automatically approve created settlements
        store_ids: Optional list of specific store IDs to process
    
    Returns:
        Dict with processing statistics
    """
    try:
        logger.info("Starting process_pending_settlements task")
        
        # Calculate cutoff time (24 hours ago)
        cutoff_time = timezone.now() - timedelta(hours=24)
        
        # Get all active stores or specific stores
        stores_qs = Store.objects.filter(status="active")
        if store_ids:
            stores_qs = stores_qs.filter(id__in=store_ids)
        
        stores = list(stores_qs.values("id", "tenant_id"))
        
        results = {
            "total_stores": len(stores),
            "settlements_created": 0,
            "settlements_approved": 0,
            "total_orders_processed": 0,
            "total_amount_settled": Decimal("0"),
            "errors": [],
        }
        
        for store in stores:
            try:
                settlement_result = _process_store_settlement(
                    store_id=store["id"],
                    cutoff_time=cutoff_time,
                    auto_approve=auto_approve,
                )
                
                if settlement_result["settlement_created"]:
                    results["settlements_created"] += 1
                    results["total_orders_processed"] += settlement_result["orders_count"]
                    results["total_amount_settled"] += settlement_result["gross_amount"]
                    
                    if settlement_result["settlement_approved"]:
                        results["settlements_approved"] += 1
                        
            except Exception as e:
                error_msg = f"Store {store['id']}: {str(e)}"
                logger.error(f"Error processing settlement for store {store['id']}: {e}")
                results["errors"].append(error_msg)
        
        logger.info(f"Completed process_pending_settlements: {results}")
        
        # Log structured batch summary
        _log_batch_summary(results)
        
        return results
        
    except Exception as exc:
        logger.exception("Fatal error in process_pending_settlements task")
        raise self.retry(exc=exc)


def _process_store_settlement(
    store_id: int,
    cutoff_time: datetime,
    auto_approve: bool = False,
) -> Dict:
    """
    Process settlement for a single store.
    
    Args:
        store_id: Store ID to process
        cutoff_time: Only process orders before this time (24h policy)
        auto_approve: Whether to auto-approve the settlement
    
    Returns:
        Dict with settlement details
    """
    # Check for unsettled paid orders respecting 24h policy
    already_settled = SettlementItem.objects.filter(order_id=OuterRef("pk"))
    
    eligible_orders = (
        Order.objects.for_tenant(store_id)
        .filter(
            payment_status="paid",
            created_at__lt=cutoff_time,  # 24h policy enforcement
        )
        .annotate(is_settled=Exists(already_settled))
        .filter(is_settled=False)
    )
    
    orders_count = eligible_orders.count()
    
    if orders_count == 0:
        return {
            "settlement_created": False,
            "settlement_approved": False,
            "orders_count": 0,
            "gross_amount": Decimal("0"),
        }
    
    # Get date range for this batch
    oldest_order = eligible_orders.order_by("created_at").first()
    newest_order = eligible_orders.order_by("-created_at").first()
    
    period_start = oldest_order.created_at.date()
    period_end = newest_order.created_at.date() + timedelta(days=1)
    
    # Create settlement
    cmd = CreateSettlementCommand(
        store_id=store_id,
        period_start=period_start,
        period_end=period_end,
    )
    
    settlement = CreateSettlementUseCase.execute(cmd)
    
    result = {
        "settlement_created": True,
        "settlement_approved": False,
        "settlement_id": settlement.id,
        "orders_count": orders_count,
        "gross_amount": settlement.gross_amount,
        "net_amount": settlement.net_amount,
    }
    
    # Auto-approve if requested
    if auto_approve:
        approve_cmd = ApproveSettlementCommand(settlement_id=settlement.id)
        ApproveSettlementUseCase.execute(approve_cmd)
        result["settlement_approved"] = True
    
    # Update ledger account
    _update_ledger_account(store_id, settlement)
    
    logger.info(f"Created settlement {settlement.id} for store {store_id}: {orders_count} orders, {settlement.gross_amount} gross")
    
    return result


def _update_ledger_account(store_id: int, settlement: Settlement) -> None:
    """Update ledger account balances after settlement creation."""
    store = Store.objects.filter(id=store_id).first()
    if not store:
        return
    
    tenant_id = store.tenant_id or store_id
    currency = "SAR"  # Default currency
    
    ledger, created = LedgerAccount.objects.get_or_create(
        store_id=store_id,
        currency=currency,
        defaults={
            "tenant_id": tenant_id,
            "available_balance": Decimal("0"),
            "pending_balance": Decimal("0"),
        },
    )
    
    # Move amount from pending to available
    if settlement.status == Settlement.STATUS_APPROVED:
        ledger.available_balance += settlement.net_amount
        ledger.save(update_fields=["available_balance"])
    else:
        # Keep in pending until approved
        ledger.pending_balance += settlement.net_amount
        ledger.save(update_fields=["pending_balance"])


@shared_task(
    name="apps.settlements.tasks.generate_daily_settlement_reports",
    bind=True,
)
def generate_daily_settlement_reports(self) -> Dict:
    """
    Generate daily settlement reports for monitoring.
    
    Returns:
        Dict with report statistics
    """
    try:
        logger.info("Starting generate_daily_settlement_reports task")
        
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        # Get yesterday's settlements
        yesterday_settlements = Settlement.objects.filter(
            created_at__date=yesterday
        ).aggregate(
            count=Count("id"),
            total_gross=Sum("gross_amount"),
            total_net=Sum("net_amount"),
            total_fees=Sum("fees_amount"),
        )
        
        # Count by status
        status_breakdown = {}
        for status, label in Settlement.STATUS_CHOICES:
            status_breakdown[status] = Settlement.objects.filter(
                created_at__date=yesterday,
                status=status,
            ).count()
        
        report = {
            "date": str(yesterday),
            "total_settlements": yesterday_settlements["count"] or 0,
            "total_gross_amount": str(yesterday_settlements["total_gross"] or Decimal("0")),
            "total_net_amount": str(yesterday_settlements["total_net"] or Decimal("0")),
            "total_fees": str(yesterday_settlements["total_fees"] or Decimal("0")),
            "status_breakdown": status_breakdown,
            "generated_at": timezone.now().isoformat(),
        }
        
        logger.info(f"Daily settlement report: {report}")
        return report
        
    except Exception as exc:
        logger.exception("Error generating daily settlement report")
        raise self.retry(exc=exc)


@shared_task(
    name="apps.settlements.tasks.reconcile_payments_and_settlements",
    bind=True,
)
def reconcile_payments_and_settlements(self, lookback_days: int = 7) -> Dict:
    """
    Reconcile payments against settlements to detect discrepancies.
    
    Compares:
    - Paid orders that are not settled (after 24h grace period)
    - Settlement items without corresponding payments
    - Amount mismatches
    
    Args:
        lookback_days: Number of days to look back for reconciliation
    
    Returns:
        Dict with reconciliation results
    """
    try:
        logger.info(f"Starting reconciliation for last {lookback_days} days")
        
        cutoff_date = timezone.now() - timedelta(days=lookback_days)
        grace_period_cutoff = timezone.now() - timedelta(hours=24)
        
        # Find paid orders not yet settled (beyond grace period)
        already_settled = SettlementItem.objects.filter(order_id=OuterRef("pk"))
        
        unsettled_paid_orders = (
            Order.objects.filter(
                payment_status="paid",
                created_at__gte=cutoff_date,
                created_at__lt=grace_period_cutoff,
            )
            .annotate(is_settled=Exists(already_settled))
            .filter(is_settled=False)
        )
        
        unsettled_count = unsettled_paid_orders.count()
        unsettled_amount = unsettled_paid_orders.aggregate(
            total=Sum("total_amount")
        )["total"] or Decimal("0")
        
        # Find settlement items without corresponding paid orders
        orphaned_items = SettlementItem.objects.filter(
            settlement__created_at__gte=cutoff_date,
        ).exclude(
            order__payment_status="paid"
        )
        
        orphaned_count = orphaned_items.count()
        
        # Find amount mismatches
        mismatches = []
        settlement_items = SettlementItem.objects.filter(
            settlement__created_at__gte=cutoff_date
        ).select_related("order")
        
        for item in settlement_items:
            if item.order_amount != item.order.total_amount:
                mismatches.append({
                    "settlement_item_id": item.id,
                    "order_id": item.order_id,
                    "settlement_amount": str(item.order_amount),
                    "order_amount": str(item.order.total_amount),
                })
        
        # Check payment intents vs settlements
        paid_intents = PaymentIntent.objects.filter(
            status="succeeded",
            created_at__gte=cutoff_date,
        ).aggregate(
            count=Count("id"),
            total=Sum("amount"),
        )
        
        settled_items = SettlementItem.objects.filter(
            settlement__created_at__gte=cutoff_date,
        ).aggregate(
            count=Count("id"),
            total=Sum("order_amount"),
        )
        
        reconciliation_result = {
            "lookback_days": lookback_days,
            "cutoff_date": cutoff_date.isoformat(),
            "unsettled_paid_orders": {
                "count": unsettled_count,
                "total_amount": str(unsettled_amount),
            },
            "orphaned_settlement_items": {
                "count": orphaned_count,
            },
            "amount_mismatches": {
                "count": len(mismatches),
                "details": mismatches[:10],  # Limit to first 10
            },
            "payment_vs_settlement": {
                "paid_intents_count": paid_intents["count"] or 0,
                "paid_intents_amount": str(paid_intents["total"] or Decimal("0")),
                "settled_items_count": settled_items["count"] or 0,
                "settled_items_amount": str(settled_items["total"] or Decimal("0")),
            },
            "reconciled_at": timezone.now().isoformat(),
        }
        
        # Log warnings for discrepancies
        if unsettled_count > 0:
            logger.warning(f"Found {unsettled_count} unsettled paid orders (amount: {unsettled_amount})")
        
        if orphaned_count > 0:
            logger.warning(f"Found {orphaned_count} orphaned settlement items")
        
        if mismatches:
            logger.warning(f"Found {len(mismatches)} amount mismatches")
        
        logger.info(f"Reconciliation completed: {reconciliation_result}")
        return reconciliation_result
        
    except Exception as exc:
        logger.exception("Error during reconciliation")
        raise self.retry(exc=exc)


@shared_task(
    name="apps.settlements.tasks.cleanup_old_settlement_logs",
)
def cleanup_old_settlement_logs(retention_days: int = 90) -> Dict:
    """
    Clean up old settlement-related logs and records.
    
    Args:
        retention_days: Number of days to retain logs
    
    Returns:
        Dict with cleanup statistics
    """
    try:
        logger.info(f"Starting cleanup of logs older than {retention_days} days")
        
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        # Example: Clean up old settlement records in 'paid' status
        old_records_deleted = SettlementRecord.objects.filter(
            status=SettlementRecord.STATUS_PAID,
            created_at__lt=cutoff_date,
        ).delete()
        
        result = {
            "cutoff_date": cutoff_date.isoformat(),
            "settlement_records_deleted": old_records_deleted[0] if old_records_deleted else 0,
            "cleaned_at": timezone.now().isoformat(),
        }
        
        logger.info(f"Cleanup completed: {result}")
        return result
        
    except Exception as exc:
        logger.exception("Error during cleanup")
        raise


@shared_task(
    name="apps.settlements.tasks.process_single_store_settlement",
)
def process_single_store_settlement(store_id: int, auto_approve: bool = False) -> Dict:
    """
    Process settlement for a single store (useful for manual triggering).
    
    Args:
        store_id: Store ID to process
        auto_approve: Whether to auto-approve the settlement
    
    Returns:
        Dict with settlement details
    """
    try:
        logger.info(f"Processing settlement for store {store_id}")
        
        cutoff_time = timezone.now() - timedelta(hours=24)
        result = _process_store_settlement(
            store_id=store_id,
            cutoff_time=cutoff_time,
            auto_approve=auto_approve,
        )
        
        logger.info(f"Store {store_id} settlement result: {result}")
        return result
        
    except Exception as exc:
        logger.exception(f"Error processing settlement for store {store_id}")
        raise


# Helper import for OuterRef
from django.db.models import Exists, OuterRef

@shared_task(
    name="apps.settlements.tasks.monitor_settlement_health",
    bind=True,
)
def monitor_settlement_health(self) -> Dict:
    """
    Monitor overall settlement system health with key metrics.
    
    Returns:
        Dict with system health metrics
    """
    try:
        logger.info("Starting settlement health monitoring")
        
        now = timezone.now()
        one_day_ago = now - timedelta(days=1)
        seven_days_ago = now - timedelta(days=7)
        
        # Recent settlements
        recent_settlements = Settlement.objects.filter(
            created_at__gte=one_day_ago
        ).aggregate(
            count=Count("id"),
            total_gross=Sum("gross_amount"),
            total_net=Sum("net_amount"),
            created=Count("id", filter=Q(status=Settlement.STATUS_CREATED)),
            approved=Count("id", filter=Q(status=Settlement.STATUS_APPROVED)),
            paid=Count("id", filter=Q(status=Settlement.STATUS_PAID)),
            failed=Count("id", filter=Q(status=Settlement.STATUS_FAILED)),
        )
        
        # Pending settlements (not yet approved)
        pending_settlements = Settlement.objects.filter(
            status=Settlement.STATUS_CREATED
        ).count()
        
        # Paid orders not yet settled (after grace period)
        grace_period = now - timedelta(hours=24)
        already_settled = SettlementItem.objects.filter(order_id=OuterRef("pk"))
        
        unsettled_paid = Order.objects.filter(
            payment_status="paid",
            created_at__lt=grace_period,
        ).annotate(is_settled=Exists(already_settled)).filter(
            is_settled=False
        ).count()
        
        # Ledger balance check
        ledger_accounts = LedgerAccount.objects.all()
        negative_balances = ledger_accounts.filter(
            Q(available_balance__lt=0) | Q(pending_balance__lt=0)
        ).count()
        
        # Settlement velocity
        settlement_velocity = Settlement.objects.filter(
            created_at__gte=seven_days_ago
        ).count() / 7  # Per day average
        
        health_status = {
            "timestamp": now.isoformat(),
            "settlement_volume_24h": {
                "count": recent_settlements["count"] or 0,
                "total_gross": str(recent_settlements["total_gross"] or Decimal("0")),
                "total_net": str(recent_settlements["total_net"] or Decimal("0")),
                "breakdown": {
                    "created": recent_settlements["created"] or 0,
                    "approved": recent_settlements["approved"] or 0,
                    "paid": recent_settlements["paid"] or 0,
                    "failed": recent_settlements["failed"] or 0,
                },
            },
            "pending_items": {
                "pending_settlements": pending_settlements,
                "unsettled_paid_orders": unsettled_paid,
            },
            "system_health": {
                "ledger_accounts_negative": negative_balances,
                "settlement_velocity_per_day": float(settlement_velocity),
            },
            "status": "healthy" if negative_balances == 0 and unsettled_paid < 100 else "warning"
        }
        
        # Log health status
        if health_status["status"] == "healthy":
            logger.info(f"Settlement system health: HEALTHY - {health_status['settlement_volume_24h']['count']} settlements in 24h")
        else:
            logger.warning(f"Settlement system health: WARNING - {health_status}")
        
        return health_status
        
    except Exception as exc:
        logger.exception("Error during settlement health monitoring")
        raise self.retry(exc=exc)


@shared_task(
    name="apps.settlements.tasks.generate_reconciliation_report",
    bind=True,
)
def generate_reconciliation_report(self, lookback_days: int = 7, send_email: bool = False) -> Dict:
    """
    Generate comprehensive reconciliation report comparing payments vs settlements.
    
    Args:
        lookback_days: Number of days to look back
        send_email: Whether to email the report (if configured)
    
    Returns:
        Dict with full reconciliation report
    """
    try:
        logger.info(f"Generating reconciliation report for last {lookback_days} days")
        
        cutoff_date = timezone.now() - timedelta(days=lookback_days)
        grace_period_cutoff = timezone.now() - timedelta(hours=24)
        
        # Payment intents
        paid_intents = PaymentIntent.objects.filter(
            status="succeeded",
            created_at__gte=cutoff_date,
        )
        
        paid_intents_agg = paid_intents.aggregate(
            count=Count("id"),
            total=Sum("amount"),
        )
        
        # Settlement items
        settled_items = SettlementItem.objects.filter(
            settlement__created_at__gte=cutoff_date,
        )
        
        settled_items_agg = settled_items.aggregate(
            count=Count("id"),
            total=Sum("order_amount"),
        )
        
        # Find unsettled paid orders beyond grace period
        already_settled = SettlementItem.objects.filter(order_id=OuterRef("pk"))
        
        unsettled_paid = Order.objects.filter(
            payment_status="paid",
            created_at__gte=cutoff_date,
            created_at__lt=grace_period_cutoff,
        ).annotate(is_settled=Exists(already_settled)).filter(
            is_settled=False
        )
        
        unsettled_agg = unsettled_paid.aggregate(
            count=Count("id"),
            total=Sum("total_amount"),
        )
        
        # Amount variance
        paid_total = paid_intents_agg["total"] or Decimal("0")
        settled_total = settled_items_agg["total"] or Decimal("0")
        variance = paid_total - settled_total
        variance_pct = (variance / paid_total * 100) if paid_total > 0 else Decimal("0")
        
        # Orphaned items (settlement items without paid orders)
        orphaned_items = settled_items.exclude(
            order__payment_status="paid"
        )
        
        orphaned_count = orphaned_items.count()
        orphaned_total = orphaned_items.aggregate(
            total=Sum("order_amount")
        )["total"] or Decimal("0")
        
        # Amount mismatches
        mismatches = []
        for item in settled_items.select_related("order")[:50]:  # Check first 50
            if item.order_amount != item.order.total_amount:
                mismatches.append({
                    "settlement_item_id": item.id,
                    "order_id": item.order_id,
                    "settlement_amount": str(item.order_amount),
                    "order_amount": str(item.order.total_amount),
                    "difference": str(item.order_amount - item.order.total_amount),
                })
        
        # Compile full report
        report = {
            "period": {
                "lookback_days": lookback_days,
                "from": cutoff_date.isoformat(),
                "to": timezone.now().isoformat(),
                "grace_period_hours": 24,
            },
            "payment_intents": {
                "count": paid_intents_agg["count"] or 0,
                "total": str(paid_total),
            },
            "settlement_items": {
                "count": settled_items_agg["count"] or 0,
                "total": str(settled_total),
            },
            "variance": {
                "amount": str(variance),
                "percentage": str(variance_pct),
                "status": "OK" if abs(variance) < Decimal("0.01") else "MISMATCH",
            },
            "unsettled_paid_orders": {
                "count": unsettled_agg["count"] or 0,
                "total": str(unsettled_agg["total"] or Decimal("0")),
                "note": "Beyond 24h grace period, should be settled",
            },
            "orphaned_items": {
                "count": orphaned_count,
                "total": str(orphaned_total),
                "status": "WARNING" if orphaned_count > 0 else "OK",
            },
            "amount_mismatches": {
                "count": len(mismatches),
                "status": "WARNING" if len(mismatches) > 0 else "OK",
                "sample": mismatches[:5],  # First 5 samples
            },
            "generated_at": timezone.now().isoformat(),
        }
        
        # Log report
        log_level = logging.WARNING if report["variance"]["status"] == "MISMATCH" or orphaned_count > 0 else logging.INFO
        logger.log(log_level, f"Reconciliation Report: {report}")
        
        return report
        
    except Exception as exc:
        logger.exception("Error generating reconciliation report")
        raise self.retry(exc=exc)


def _log_batch_summary(batch_summary: Dict) -> None:
    """
    Log settlement batch summary with structured format.
    
    Args:
        batch_summary: Dict with batch statistics
    """
    summary_log = f"""
    ╔═══════════════════════════════════════════════════════════════╗
    ║ SETTLEMENT BATCH SUMMARY                                      ║
    ╠═══════════════════════════════════════════════════════════════╣
    ║ Stores Processed:        {str(batch_summary.get('total_stores', 0)):>30} ║
    ║ Settlements Created:     {str(batch_summary.get('settlements_created', 0)):>30} ║
    ║ Settlements Approved:    {str(batch_summary.get('settlements_approved', 0)):>30} ║
    ║ Orders Processed:        {str(batch_summary.get('total_orders_processed', 0)):>30} ║
    ║ Total Amount Settled:    ${str(batch_summary.get('total_amount_settled', '0')):>29} ║
    ║ Errors:                  {str(len(batch_summary.get('errors', []))):>30} ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    logger.info(summary_log)
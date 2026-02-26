"""
Admin monitoring views for settlement processing.

This module provides API endpoints for monitoring settlement health,
triggering manual settlement runs, and viewing reconciliation reports.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.settlements.application.reconciliation import ReconciliationService
from apps.settlements.models import Settlement, SettlementItem
from apps.settlements.tasks import (
    process_single_store_settlement,
    process_pending_settlements,
)


@staff_member_required
@require_http_methods(["GET"])
def settlement_dashboard(request) -> JsonResponse:
    """
    Get settlement dashboard overview.
    
    Returns:
        JSON with settlement statistics and health metrics
    """
    store_id = request.GET.get("store_id")
    if store_id:
        store_id = int(store_id)
    
    # Get recent settlements
    settlements_qs = Settlement.objects.all()
    if store_id:
        settlements_qs = settlements_qs.filter(store_id=store_id)
    
    recent_settlements = (
        settlements_qs
        .order_by("-created_at")[:10]
        .values(
            "id",
            "store_id",
            "period_start",
            "period_end",
            "gross_amount",
            "net_amount",
            "status",
            "created_at",
        )
    )
    
    # Get status breakdown
    status_counts = {}
    for status, label in Settlement.STATUS_CHOICES:
        qs = settlements_qs.filter(status=status)
        status_counts[status] = {
            "count": qs.count(),
            "total_amount": str(
                qs.aggregate(total=Sum("net_amount"))["total"] or Decimal("0")
            ),
        }
    
    # Get health score
    health_metrics = ReconciliationService.calculate_settlement_health_score(
        store_id=store_id
    )
    
    # Get unsettled orders
    unsettled_orders = ReconciliationService.get_unsettled_orders_details(
        store_id=store_id,
        limit=20,
    )
    
    response_data = {
        "recent_settlements": [
            {
                **settlement,
                "period_start": str(settlement["period_start"]),
                "period_end": str(settlement["period_end"]),
                "gross_amount": str(settlement["gross_amount"]),
                "net_amount": str(settlement["net_amount"]),
                "created_at": settlement["created_at"].isoformat(),
            }
            for settlement in recent_settlements
        ],
        "status_breakdown": status_counts,
        "health_metrics": health_metrics,
        "unsettled_orders": unsettled_orders,
        "timestamp": timezone.now().isoformat(),
    }
    
    return JsonResponse(response_data)


@staff_member_required
@require_http_methods(["GET"])
def reconciliation_report(request) -> JsonResponse:
    """
    Get reconciliation report comparing payments vs settlements.
    
    Query params:
        - lookback_days: Number of days to look back (default: 7)
        - store_id: Optional store ID to filter by
    
    Returns:
        JSON with reconciliation report
    """
    lookback_days = int(request.GET.get("lookback_days", 7))
    store_id = request.GET.get("store_id")
    if store_id:
        store_id = int(store_id)
    
    report = ReconciliationService.generate_reconciliation_report(
        lookback_days=lookback_days,
        store_id=store_id,
    )
    
    return JsonResponse(report.to_dict())


@staff_member_required
@require_http_methods(["POST"])
def trigger_settlement_run(request) -> JsonResponse:
    """
    Manually trigger settlement processing.
    
    POST data (JSON):
        - store_id: Optional specific store ID
        - auto_approve: Whether to auto-approve settlements (default: false)
    
    Returns:
        JSON with task ID and status
    """
    import json
    
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = {}
    
    store_id = data.get("store_id")
    auto_approve = data.get("auto_approve", False)
    
    if store_id:
        # Trigger single store settlement
        task = process_single_store_settlement.delay(
            store_id=int(store_id),
            auto_approve=auto_approve,
        )
        
        return JsonResponse({
            "status": "triggered",
            "task_id": task.id,
            "store_id": store_id,
            "auto_approve": auto_approve,
            "message": f"Settlement processing triggered for store {store_id}",
        })
    else:
        # Trigger all stores settlement
        store_ids = data.get("store_ids")
        task = process_pending_settlements.delay(
            auto_approve=auto_approve,
            store_ids=store_ids,
        )
        
        return JsonResponse({
            "status": "triggered",
            "task_id": task.id,
            "auto_approve": auto_approve,
            "message": "Settlement processing triggered for all stores" if not store_ids else f"Settlement processing triggered for {len(store_ids)} stores",
        })


@staff_member_required
@require_http_methods(["GET"])
def task_status(request, task_id: str) -> JsonResponse:
    """
    Get status of a Celery task.
    
    Args:
        task_id: Celery task ID
    
    Returns:
        JSON with task status
    """
    from celery.result import AsyncResult
    
    task = AsyncResult(task_id)
    
    response_data = {
        "task_id": task_id,
        "status": task.status,
        "ready": task.ready(),
        "successful": task.successful() if task.ready() else None,
    }
    
    if task.ready():
        if task.successful():
            response_data["result"] = task.result
        else:
            response_data["error"] = str(task.info)
    
    return JsonResponse(response_data)


@staff_member_required
@require_http_methods(["GET"])
def settlement_health(request) -> JsonResponse:
    """
    Get settlement health score and metrics.
    
    Query params:
        - store_id: Optional store ID to filter by
    
    Returns:
        JSON with health score and metrics
    """
    store_id = request.GET.get("store_id")
    if store_id:
        store_id = int(store_id)
    
    health_metrics = ReconciliationService.calculate_settlement_health_score(
        store_id=store_id
    )
    
    return JsonResponse(health_metrics)


# Helper import for Sum
from django.db.models import Sum

"""
Settlement automation API views.

Merchant APIs:
- GET /api/settlements/batches/
- GET /api/settlements/batches/{id}/

Admin APIs:
- GET /api/admin/settlements/batches/
- GET /api/admin/settlements/batches/{id}/
- GET /api/admin/settlements/reconciliation/
- POST /api/admin/settlements/run-manual/
- POST /api/admin/settlements/health/
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from apps.settlements.models import SettlementBatch, ReconciliationReport, SettlementRunLog
from apps.settlements.serializers_automation import (
    SettlementBatchSerializer,
    ReconciliationReportSerializer,
    SettlementRunLogSerializer,
)
from apps.settlements.tasks_automation import (
    automation_process_pending_settlements,
    automation_run_reconciliation,
    automation_monitor_settlement_health,
)


class MerchantSettlementBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Merchant view of settlement batches.
    
    Only shows batches for their own store.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = SettlementBatchSerializer
    filterset_fields = ["status", "created_at"]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ["-created_at", "status", "total_amount"]
    ordering = ["-created_at"]
    
    def get_queryset(self):
        """Filter batches for current user's store."""
        user = self.request.user
        if hasattr(user, "merchant"):
            return SettlementBatch.objects.filter(
                store=user.merchant.store
            ).prefetch_related("items")
        return SettlementBatch.objects.none()
    
    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """Get batch summary with statistics."""
        batch = self.get_object()
        
        data = {
            "batch_id": batch.id,
            "batch_reference": batch.batch_reference,
            "status": batch.status,
            "total_orders": batch.total_orders,
            "orders_succeeded": batch.orders_succeeded,
            "orders_failed": batch.orders_failed,
            "total_amount": str(batch.total_amount),
            "total_fees": str(batch.total_fees),
            "total_net": str(batch.total_net),
            "created_at": batch.created_at,
            "completed_at": batch.completed_at,
            "duration_ms": batch.duration_ms,
        }
        
        return Response(data)


class AdminSettlementBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin view of all settlement batches.
    
    Shows all batches across all stores with management options.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = SettlementBatchSerializer
    filterset_fields = ["status", "store", "created_at"]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ["-created_at", "status", "total_amount"]
    ordering = ["-created_at"]
    
    def get_queryset(self):
        """Return all batches for admin."""
        return SettlementBatch.objects.all().prefetch_related(
            "items"
        ).select_related("store")
    
    @action(detail=False, methods=["post"])
    def run_manual(self, request):
        """
        Manually trigger settlement batch processing.
        
        POST /admin/settlements/batches/run_manual/
        {
            "store_ids": [1, 2, 3]  // optional
        }
        """
        store_ids = request.data.get("store_ids")
        
        # Trigger async task
        task = automation_process_pending_settlements.delay(
            store_ids=store_ids
        )
        
        return Response({
            "task_id": task.id,
            "message": "Settlement batch processing started",
            "status": "processing",
        }, status=status.HTTP_202_ACCEPTED)
    
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get settlement batch statistics."""
        from django.db.models import Sum, Count, Q
        from datetime import timedelta
        from django.utils import timezone
        
        now = timezone.now()
        one_day_ago = now - timedelta(days=1)
        seven_days_ago = now - timedelta(days=7)
        
        batches_24h = SettlementBatch.objects.filter(
            created_at__gte=one_day_ago
        ).aggregate(
            count=Count("id"),
            total_amount=Sum("total_amount"),
            completed=Count("id", filter=Q(status=SettlementBatch.STATUS_COMPLETED)),
            failed=Count("id", filter=Q(status=SettlementBatch.STATUS_FAILED)),
        )
        
        batches_7d = SettlementBatch.objects.filter(
            created_at__gte=seven_days_ago
        ).aggregate(
            count=Count("id"),
            total_amount=Sum("total_amount"),
        )
        
        return Response({
            "period_24h": {
                "batch_count": batches_24h["count"] or 0,
                "total_amount": str(batches_24h["total_amount"] or 0),
                "completed": batches_24h["completed"] or 0,
                "failed": batches_24h["failed"] or 0,
            },
            "period_7d": {
                "batch_count": batches_7d["count"] or 0,
                "total_amount": str(batches_7d["total_amount"] or 0),
            },
        })


class AdminReconciliationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin view of reconciliation reports.
    
    Shows discrepancies between payments and settlements.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = ReconciliationReportSerializer
    filterset_fields = ["status", "store", "period_start", "period_end"]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering = ["-created_at"]
    
    def get_queryset(self):
        """Return all reconciliation reports."""
        return ReconciliationReport.objects.all().select_related("store")
    
    @action(detail=False, methods=["post"])
    def run_manual(self, request):
        """
        Manually trigger reconciliation.
        
        POST /admin/reconciliation/run_manual/
        {
            "store_ids": [1, 2]  // optional
        }
        """
        store_ids = request.data.get("store_ids")
        
        task = automation_run_reconciliation.delay(store_ids=store_ids)
        
        return Response({
            "task_id": task.id,
            "message": "Reconciliation started",
            "status": "processing",
        }, status=status.HTTP_202_ACCEPTED)
    
    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Get reconciliation summary."""
        from django.db.models import Count, Q
        
        all_reports = ReconciliationReport.objects.all()
        
        summary = {
            "total_reports": all_reports.count(),
            "ok": all_reports.filter(status=ReconciliationReport.STATUS_OK).count(),
            "warning": all_reports.filter(
                status=ReconciliationReport.STATUS_WARNING
            ).count(),
            "error": all_reports.filter(
                status=ReconciliationReport.STATUS_ERROR
            ).count(),
        }
        
        return Response(summary)


class AdminSettlementHealthViewSet(viewsets.ViewSet):
    """
    Admin view for settlement system health.
    
    Monitors:
    - Batch processing health
    - Reconciliation status
    - System alerts
    """
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=["get"])
    def monitor(self, request):
        """
        Get current settlement system health.
        
        GET /admin/health/monitor/
        """
        task = automation_monitor_settlement_health.delay()
        
        return Response({
            "task_id": task.id,
            "message": "Health check started",
            "status": "processing",
        }, status=status.HTTP_202_ACCEPTED)
    
    @action(detail=False, methods=["get"])
    def logs(self, request):
        """
        Get recent settlement task logs.
        
        GET /admin/health/logs/
        ?task_name=...&status=...&limit=10
        """
        from datetime import timedelta
        from django.utils import timezone
        
        task_name = request.query_params.get("task_name")
        task_status = request.query_params.get("status")
        limit = int(request.query_params.get("limit", "20"))
        
        logs = SettlementRunLog.objects.all()
        
        if task_name:
            logs = logs.filter(task_name=task_name)
        
        if task_status:
            logs = logs.filter(status=task_status)
        
        logs = logs.order_by("-created_at")[:limit]
        
        serializer = SettlementRunLogSerializer(logs, many=True)
        
        return Response({
            "logs": serializer.data,
            "count": len(logs),
        })

"""
Settlement automation service.

Handles:
- Batch creation and processing
- Idempotency checks
- Reconciliation logic
- Settlement status tracking
"""

from __future__ import annotations

import logging
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from django.db import transaction
from django.db.models import Exists, OuterRef, Sum, Count, Q
from django.utils import timezone
from django.conf import settings

from apps.orders.models import Order
from apps.settlements.models import (
    Settlement,
    SettlementBatch,
    SettlementBatchItem,
    SettlementRunLog,
    ReconciliationReport,
    SettlementRecord,
    LedgerAccount,
)
from apps.stores.models import Store
from apps.wallet.services.accounting_service import AccountingService

logger = logging.getLogger(__name__)


class SettlementAutomationService:
    """
    Service for automating settlement batch processing.
    
    Key features:
    - Idempotent batch creation (safe to retry)
    - 24-hour SLA enforcement
    - Atomic transactions
    - Full audit logging
    """
    
    def __init__(self):
        self.settlement_delay_hours = getattr(
            settings, "SETTLEMENT_DELAY_HOURS", 24
        )
        self.batch_size = getattr(settings, "SETTLEMENT_BATCH_SIZE", 100)
        self.batch_max_orders = getattr(
            settings, "SETTLEMENT_BATCH_MAX_ORDERS", 1000
        )
        self.auto_approve = getattr(settings, "SETTLEMENT_AUTO_APPROVE", False)
        self.detailed_logging = getattr(
            settings, "SETTLEMENT_DETAILED_LOGGING", True
        )
    
    @transaction.atomic
    def process_store_settlements(
        self,
        store_id: int,
        cutoff_time: Optional[datetime] = None,
    ) -> Dict:
        """
        Process pending settlements for a single store.
        
        Args:
            store_id: Store to process
            cutoff_time: Only process orders before this time (defaults to now - 24h)
        
        Returns:
            Dict with processing results
        """
        if cutoff_time is None:
            cutoff_time = timezone.now() - timedelta(hours=self.settlement_delay_hours)
        
        store = Store.objects.filter(id=store_id).first()
        if not store:
            logger.warning(f"Store {store_id} not found")
            return {
                "store_id": store_id,
                "success": False,
                "reason": "Store not found",
            }
        
        # Find eligible orders
        eligible_orders = self._get_eligible_orders(store_id, cutoff_time)
        orders_count = eligible_orders.count()
        
        if orders_count == 0:
            logger.info(f"No eligible orders for store {store_id}")
            return {
                "store_id": store_id,
                "success": True,
                "batch_created": False,
                "reason": "No eligible orders",
            }
        
        # Batch in chunks
        order_ids = list(eligible_orders.values_list("id", flat=True))
        batches_created = 0
        total_amount = Decimal("0")
        
        for i in range(0, len(order_ids), self.batch_size):
            chunk_ids = order_ids[i : i + self.batch_size]
            batch_result = self._create_settlement_batch(
                store_id=store_id,
                order_ids=chunk_ids,
                batch_num=batches_created + 1,
            )
            
            if batch_result["success"]:
                batches_created += 1
                total_amount += batch_result["total_amount"]
            else:
                logger.error(
                    f"Failed to create batch for store {store_id}: "
                    f"{batch_result['reason']}"
                )
        
        return {
            "store_id": store_id,
            "success": True,
            "batches_created": batches_created,
            "orders_processed": orders_count,
            "total_amount": str(total_amount),
        }
    
    def _get_eligible_orders(
        self,
        store_id: int,
        cutoff_time: datetime,
    ) -> object:
        """
        Get orders eligible for settlement.
        
        Criteria:
        - Payment status = confirmed/paid
        - Not already settled
        - Older than cutoff time (24h SLA)
        
        Returns:
            QuerySet of eligible orders
        """
        # Already settled orders (to exclude)
        already_settled = SettlementBatchItem.objects.filter(
            order_id=OuterRef("pk"),
            status__in=[
                SettlementBatchItem.STATUS_PROCESSED,
                SettlementBatchItem.STATUS_INCLUDED,
            ],
        )
        
        return (
            Order.objects.for_tenant(store_id)
            .filter(
                Q(payment_status="confirmed") | Q(payment_status="paid"),
                created_at__lt=cutoff_time,
            )
            .annotate(is_settled=Exists(already_settled))
            .filter(is_settled=False)
        )
    
    @transaction.atomic
    def _create_settlement_batch(
        self,
        store_id: int,
        order_ids: List[int],
        batch_num: int = 1,
    ) -> Dict:
        """
        Create a settlement batch for a set of orders.
        
        Idempotent: If batch with same parameters already exists, returns it.
        
        Args:
            store_id: Store ID
            order_ids: List of order IDs to include
            batch_num: Batch sequence number for reference
        
        Returns:
            Dict with batch details
        """
        if not order_ids:
            return {"success": False, "reason": "No order IDs provided"}
        
        # Generate deterministic idempotency key using SHA256 (not Python hash())
        sorted_ids = sorted(order_ids)
        ids_str = ",".join(str(id_) for id_ in sorted_ids)
        deterministic_hash = hashlib.sha256(ids_str.encode()).hexdigest()
        batch_ref = f"BATCH-{store_id}-{timezone.now().strftime('%Y%m%d')}-{batch_num:03d}"
        idempotency_key = f"{batch_ref}-{deterministic_hash}"
        
        # Check if batch already exists (idempotency) - with select_for_update
        existing_batch = SettlementBatch.objects.select_for_update().filter(
            idempotency_key=idempotency_key
        ).first()
        
        if existing_batch:
            logger.info(
                f"Batch {batch_ref} already exists (idempotent), "
                f"returning existing batch {existing_batch.id}"
            )
            return {
                "success": True,
                "batch_id": existing_batch.id,
                "batch_reference": existing_batch.batch_reference,
                "total_amount": str(existing_batch.total_amount),
                "idempotent_reuse": True,
            }
        
        # Fetch orders with select_for_update to prevent double-settlement
        orders = Order.objects.select_for_update().filter(
            id__in=order_ids
        ).select_related("store")
        
        if not orders.exists():
            return {"success": False, "reason": "No orders found"}
        
        # Calculate batch totals
        total_amount = Decimal("0")
        total_fees = Decimal("0")
        batch_items = []
        
        for order in orders:
            # Calculate fee (will use wallet service for accurate calc)
            fee = self._calculate_order_fee(order)
            net_amount = order.total_amount - fee
            
            total_amount += order.total_amount
            total_fees += fee
            
            batch_items.append({
                "order": order,
                "order_amount": order.total_amount,
                "calculated_fee": fee,
                "calculated_net": net_amount,
            })
        
        total_net = total_amount - total_fees
        
        # Create batch
        try:
            batch = SettlementBatch.objects.create(
                store_id=store_id,
                batch_reference=batch_ref,
                idempotency_key=idempotency_key,
                total_orders=len(batch_items),
                total_amount=total_amount,
                total_fees=total_fees,
                total_net=total_net,
                status=SettlementBatch.STATUS_PROCESSING,
            )
            
            # Create batch items
            for item_data in batch_items:
                SettlementBatchItem.objects.create(
                    batch=batch,
                    order=item_data["order"],
                    order_amount=item_data["order_amount"],
                    calculated_fee=item_data["calculated_fee"],
                    calculated_net=item_data["calculated_net"],
                    status=SettlementBatchItem.STATUS_INCLUDED,
                )
            
            if self.detailed_logging:
                logger.info(
                    f"Created batch {batch_ref}: "
                    f"{batch.total_orders} orders, "
                    f"${batch.total_amount} total"
                )
            
            return {
                "success": True,
                "batch_id": batch.id,
                "batch_reference": batch_ref,
                "total_amount": str(total_amount),
                "total_orders": len(batch_items),
            }
        
        except Exception as e:
            logger.exception(f"Error creating settlement batch {batch_ref}: {e}")
            return {
                "success": False,
                "reason": str(e),
            }
    
    def _calculate_order_fee(self, order: Order) -> Decimal:
        """
        Calculate fee for an order.
        
        Uses accounting service for consistent fee calculation.
        
        Args:
            order: Order instance
        
        Returns:
            Decimal fee amount
        """
        try:
            accounting = AccountingService()
            fee_policy = accounting.get_active_fee_policy(
                store_id=order.store_id,
            )
            
            fee = accounting.calculate_fee(
                amount=order.total_amount,
                fee_policy=fee_policy,
            )
            
            return fee
        except Exception as e:
            logger.warning(
                f"Error calculating fee for order {order.id}: {e}, "
                f"using flat 2.5%"
            )
            return order.total_amount * Decimal("0.025")
    
    def mark_batch_completed(
        self,
        batch_id: int,
        succeeded: int,
        failed: int,
    ) -> None:
        """
        Mark batch as completed.
        
        Args:
            batch_id: Batch ID
            succeeded: Number of orders that succeeded
            failed: Number of orders that failed
        """
        batch = SettlementBatch.objects.filter(id=batch_id).first()
        if not batch:
            return
        
        batch.orders_succeeded = succeeded
        batch.orders_failed = failed
        
        # Determine status
        if failed == 0:
            batch.status = SettlementBatch.STATUS_COMPLETED
        elif succeeded == 0:
            batch.status = SettlementBatch.STATUS_FAILED
        else:
            batch.status = SettlementBatch.STATUS_PARTIAL
        
        batch.completed_at = timezone.now()
        batch.duration_ms = int(
            (batch.completed_at - batch.started_at).total_seconds() * 1000
        )
        batch.save(
            update_fields=[
                "status",
                "orders_succeeded",
                "orders_failed",
                "completed_at",
                "duration_ms",
            ]
        )
        
        logger.info(
            f"Batch {batch.batch_reference} marked "
            f"{batch.status}: {succeeded}✓ {failed}✗"
        )
    
    def log_settlement_run(
        self,
        task_name: str,
        task_id: Optional[str],
        status: str,
        started_at: datetime,
        completed_at: Optional[datetime] = None,
        message: str = "",
        payload: Optional[Dict] = None,
        error_trace: str = "",
        orders_processed: int = 0,
        batches_created: int = 0,
        total_amount: Decimal = Decimal("0"),
        store_id: Optional[int] = None,
    ) -> None:
        """
        Log a settlement run for audit trail and monitoring.
        
        Args:
            task_name: Name of the task that ran
            task_id: Celery task ID
            status: 'started', 'completed', or 'failed'
            started_at: When the run started
            completed_at: When the run ended
            message: Summary message
            payload: Additional metadata
            error_trace: Full stack trace if failed
            orders_processed: Number of orders processed
            batches_created: Number of batches created
            total_amount: Total amount settled
            store_id: Store ID (optional, for per-store runs)
        """
        try:
            duration_ms = None
            if completed_at:
                duration_ms = int(
                    (completed_at - started_at).total_seconds() * 1000
                )
            
            store = None
            if store_id:
                store = Store.objects.filter(id=store_id).first()
            
            SettlementRunLog.objects.create(
                task_name=task_name,
                task_id=task_id,
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                message=message,
                payload_json=payload or {},
                error_trace=error_trace,
                orders_processed=orders_processed,
                batches_created=batches_created,
                total_amount=total_amount,
                store=store,
            )
        except Exception as e:
            logger.exception(f"Error logging settlement run: {e}")


class ReconciliationService:
    """
    Service for reconciling payments vs settlements.
    
    Detects:
    - Unsettled paid orders (beyond grace period)
    - Orphaned settlement items
    - Amount discrepancies
    """
    
    def __init__(self):
        self.lookback_days = getattr(
            settings, "SETTLEMENT_RECONCILIATION_LOOKBACK_DAYS", 7
        )
        self.grace_period_hours = getattr(
            settings, "SETTLEMENT_DELAY_HOURS", 24
        )
    
    @transaction.atomic
    def run_reconciliation(
        self,
        store_id: Optional[int] = None,
        lookback_days: Optional[int] = None,
    ) -> Dict:
        """
        Run comprehensive reconciliation.
        
        Args:
            store_id: Optional store to reconcile (None = all stores)
            lookback_days: Days to look back (default: 7)
        
        Returns:
            Dict with reconciliation results
        """
        if lookback_days is None:
            lookback_days = self.lookback_days
        
        cutoff_date = timezone.now() - timedelta(days=lookback_days)
        grace_period_cutoff = timezone.now() - timedelta(
            hours=self.grace_period_hours
        )
        
        stores = Store.objects.all()
        if store_id:
            stores = stores.filter(id=store_id)
        
        results = {
            "stores_reconciled": 0,
            "reports_created": 0,
            "discrepancies_found": 0,
        }
        
        for store in stores:
            report = self._reconcile_store(
                store=store,
                cutoff_date=cutoff_date,
                grace_period_cutoff=grace_period_cutoff,
            )
            
            results["stores_reconciled"] += 1
            if report["discrepancy_amount"] != Decimal("0"):
                results["discrepancies_found"] += 1
        
        return results
    
    def _reconcile_store(
        self,
        store: Store,
        cutoff_date: datetime,
        grace_period_cutoff: datetime,
    ) -> Dict:
        """
        Reconcile a single store.
        
        Returns:
            Dict with report details
        """
        period_start = cutoff_date.date()
        period_end = timezone.now().date()
        
        # Get expected total (paid orders)
        expected = Order.objects.for_tenant(store.id).filter(
            Q(payment_status="confirmed") | Q(payment_status="paid"),
            created_at__gte=cutoff_date,
        ).aggregate(total=Sum("total_amount"))
        
        expected_total = expected["total"] or Decimal("0")
        
        # Get settled total
        already_settled = SettlementBatchItem.objects.filter(
            order_id=OuterRef("pk")
        )
        
        settled = SettlementBatchItem.objects.filter(
            batch__store=store,
            batch__created_at__gte=cutoff_date,
        ).aggregate(total=Sum("order_amount"))
        
        settled_total = settled["total"] or Decimal("0")
        
        # Calculate discrepancy
        discrepancy = expected_total - settled_total
        discrepancy_pct = (
            (discrepancy / expected_total * 100)
            if expected_total > 0
            else Decimal("0")
        )
        
        # Find unsettled paid orders (beyond grace period)
        unsettled_paid = (
            Order.objects.for_tenant(store.id)
            .filter(
                Q(payment_status="confirmed") | Q(payment_status="paid"),
                created_at__gte=cutoff_date,
                created_at__lt=grace_period_cutoff,
            )
            .annotate(is_settled=Exists(already_settled))
            .filter(is_settled=False)
        )
        
        unsettled_count = unsettled_paid.count()
        
        # Find orphaned items
        orphaned_items = SettlementBatchItem.objects.filter(
            batch__store=store,
            batch__created_at__gte=cutoff_date,
        ).exclude(order__payment_status__in=["confirmed", "paid"])
        
        orphaned_count = orphaned_items.count()
        
        # Determine status
        if discrepancy == Decimal("0") and orphaned_count == 0:
            status = ReconciliationReport.STATUS_OK
        elif abs(discrepancy) < Decimal("10"):
            status = ReconciliationReport.STATUS_WARNING
        else:
            status = ReconciliationReport.STATUS_ERROR
        
        # Create report
        report = ReconciliationReport.objects.create(
            store=store,
            period_start=period_start,
            period_end=period_end,
            expected_total=expected_total,
            settled_total=settled_total,
            discrepancy=discrepancy,
            discrepancy_percentage=discrepancy_pct,
            unsettled_orders_count=unsettled_count,
            orphaned_items_count=orphaned_count,
            status=status,
            findings=[
                {
                    "type": "unsettled_paid_orders",
                    "count": unsettled_count,
                    "note": f"{unsettled_count} paid orders not settled beyond grace period",
                },
                {
                    "type": "orphaned_settlement_items",
                    "count": orphaned_count,
                    "note": "Settlement items without corresponding paid orders",
                },
                {
                    "type": "discrepancy",
                    "amount": str(discrepancy),
                    "percentage": str(discrepancy_pct),
                    "note": f"Expected {expected_total}, settled {settled_total}",
                },
            ],
        )
        
        if status != ReconciliationReport.STATUS_OK:
            logger.warning(
                f"Reconciliation {status.upper()} for store {store.id}: "
                f"expected {expected_total}, settled {settled_total}, "
                f"discrepancy {discrepancy}"
            )
        
        return {
            "store_id": store.id,
            "report_id": report.id,
            "status": status,
            "expected_total": str(expected_total),
            "settled_total": str(settled_total),
            "discrepancy_amount": discrepancy,
            "unsettled_orders": unsettled_count,
            "orphaned_items": orphaned_count,
        }

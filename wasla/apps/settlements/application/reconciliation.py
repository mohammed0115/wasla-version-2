"""
Reconciliation service for settlements.

This module provides utilities for comparing payments against settlements
to ensure data integrity and detect discrepancies.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List

from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.utils import timezone

from apps.orders.models import Order
from apps.payments.models import PaymentAttempt, PaymentIntent
from apps.settlements.models import Settlement, SettlementItem, SettlementRecord


@dataclass
class ReconciliationReport:
    """Report containing reconciliation results."""
    
    lookback_days: int
    cutoff_date: datetime
    unsettled_paid_orders_count: int
    unsettled_paid_orders_amount: Decimal
    orphaned_settlement_items_count: int
    amount_mismatches: List[Dict]
    payment_intents_count: int
    payment_intents_amount: Decimal
    settled_items_count: int
    settled_items_amount: Decimal
    reconciled_at: datetime
    
    @property
    def has_discrepancies(self) -> bool:
        """Check if there are any discrepancies."""
        return (
            self.unsettled_paid_orders_count > 0
            or self.orphaned_settlement_items_count > 0
            or len(self.amount_mismatches) > 0
        )
    
    @property
    def payment_settlement_diff(self) -> Decimal:
        """Calculate difference between payments and settlements."""
        return self.payment_intents_amount - self.settled_items_amount
    
    def to_dict(self) -> Dict:
        """Convert report to dictionary format."""
        return {
            "lookback_days": self.lookback_days,
            "cutoff_date": self.cutoff_date.isoformat(),
            "unsettled_paid_orders": {
                "count": self.unsettled_paid_orders_count,
                "total_amount": str(self.unsettled_paid_orders_amount),
            },
            "orphaned_settlement_items": {
                "count": self.orphaned_settlement_items_count,
            },
            "amount_mismatches": {
                "count": len(self.amount_mismatches),
                "details": self.amount_mismatches,
            },
            "payment_vs_settlement": {
                "paid_intents_count": self.payment_intents_count,
                "paid_intents_amount": str(self.payment_intents_amount),
                "settled_items_count": self.settled_items_count,
                "settled_items_amount": str(self.settled_items_amount),
                "difference": str(self.payment_settlement_diff),
            },
            "has_discrepancies": self.has_discrepancies,
            "reconciled_at": self.reconciled_at.isoformat(),
        }


class ReconciliationService:
    """Service for reconciling payments and settlements."""
    
    @staticmethod
    def generate_reconciliation_report(
        lookback_days: int = 7,
        store_id: int = None,
    ) -> ReconciliationReport:
        """
        Generate comprehensive reconciliation report.
        
        Args:
            lookback_days: Number of days to look back
            store_id: Optional store ID to filter by
        
        Returns:
            ReconciliationReport object
        """
        cutoff_date = timezone.now() - timedelta(days=lookback_days)
        grace_period_cutoff = timezone.now() - timedelta(hours=24)
        
        # Find paid orders not yet settled (beyond grace period)
        unsettled_data = ReconciliationService._find_unsettled_orders(
            cutoff_date=cutoff_date,
            grace_period_cutoff=grace_period_cutoff,
            store_id=store_id,
        )
        
        # Find orphaned settlement items
        orphaned_count = ReconciliationService._find_orphaned_settlements(
            cutoff_date=cutoff_date,
            store_id=store_id,
        )
        
        # Find amount mismatches
        mismatches = ReconciliationService._find_amount_mismatches(
            cutoff_date=cutoff_date,
            store_id=store_id,
        )
        
        # Compare payment intents vs settlements
        payment_data = ReconciliationService._get_payment_summary(
            cutoff_date=cutoff_date,
            store_id=store_id,
        )
        
        settlement_data = ReconciliationService._get_settlement_summary(
            cutoff_date=cutoff_date,
            store_id=store_id,
        )
        
        return ReconciliationReport(
            lookback_days=lookback_days,
            cutoff_date=cutoff_date,
            unsettled_paid_orders_count=unsettled_data["count"],
            unsettled_paid_orders_amount=unsettled_data["amount"],
            orphaned_settlement_items_count=orphaned_count,
            amount_mismatches=mismatches,
            payment_intents_count=payment_data["count"],
            payment_intents_amount=payment_data["amount"],
            settled_items_count=settlement_data["count"],
            settled_items_amount=settlement_data["amount"],
            reconciled_at=timezone.now(),
        )
    
    @staticmethod
    def _find_unsettled_orders(
        cutoff_date: datetime,
        grace_period_cutoff: datetime,
        store_id: int = None,
    ) -> Dict:
        """Find paid orders that haven't been settled yet."""
        already_settled = SettlementItem.objects.filter(order_id=OuterRef("pk"))
        
        qs = Order.objects.filter(
            payment_status="paid",
            created_at__gte=cutoff_date,
            created_at__lt=grace_period_cutoff,
        ).annotate(
            is_settled=Exists(already_settled)
        ).filter(
            is_settled=False
        )
        
        if store_id:
            qs = qs.filter(store_id=store_id)
        
        result = qs.aggregate(
            count=Count("id"),
            total=Sum("total_amount"),
        )
        
        return {
            "count": result["count"] or 0,
            "amount": result["total"] or Decimal("0"),
        }
    
    @staticmethod
    def _find_orphaned_settlements(
        cutoff_date: datetime,
        store_id: int = None,
    ) -> int:
        """Find settlement items without corresponding paid orders."""
        qs = SettlementItem.objects.filter(
            settlement__created_at__gte=cutoff_date,
        ).exclude(
            order__payment_status="paid"
        )
        
        if store_id:
            qs = qs.filter(settlement__store_id=store_id)
        
        return qs.count()
    
    @staticmethod
    def _find_amount_mismatches(
        cutoff_date: datetime,
        store_id: int = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Find settlement items with amount mismatches."""
        qs = SettlementItem.objects.filter(
            settlement__created_at__gte=cutoff_date
        ).select_related("order", "settlement")
        
        if store_id:
            qs = qs.filter(settlement__store_id=store_id)
        
        mismatches = []
        for item in qs[:limit]:
            if item.order_amount != item.order.total_amount:
                mismatches.append({
                    "settlement_item_id": item.id,
                    "settlement_id": item.settlement_id,
                    "order_id": item.order_id,
                    "settlement_amount": str(item.order_amount),
                    "order_amount": str(item.order.total_amount),
                    "difference": str(item.order_amount - item.order.total_amount),
                })
        
        return mismatches
    
    @staticmethod
    def _get_payment_summary(
        cutoff_date: datetime,
        store_id: int = None,
    ) -> Dict:
        """Get summary of successful payments."""
        qs = PaymentIntent.objects.filter(
            status="succeeded",
            created_at__gte=cutoff_date,
        )
        
        if store_id:
            qs = qs.filter(store_id=store_id)
        
        result = qs.aggregate(
            count=Count("id"),
            total=Sum("amount"),
        )
        
        return {
            "count": result["count"] or 0,
            "amount": result["total"] or Decimal("0"),
        }
    
    @staticmethod
    def _get_settlement_summary(
        cutoff_date: datetime,
        store_id: int = None,
    ) -> Dict:
        """Get summary of settlement items."""
        qs = SettlementItem.objects.filter(
            settlement__created_at__gte=cutoff_date,
        )
        
        if store_id:
            qs = qs.filter(settlement__store_id=store_id)
        
        result = qs.aggregate(
            count=Count("id"),
            total=Sum("order_amount"),
        )
        
        return {
            "count": result["count"] or 0,
            "amount": result["total"] or Decimal("0"),
        }
    
    @staticmethod
    def get_unsettled_orders_details(
        store_id: int = None,
        limit: int = 100,
    ) -> List[Dict]:
        """
        Get detailed list of unsettled orders.
        
        Args:
            store_id: Optional store ID to filter by
            limit: Maximum number of orders to return
        
        Returns:
            List of order details
        """
        grace_period_cutoff = timezone.now() - timedelta(hours=24)
        already_settled = SettlementItem.objects.filter(order_id=OuterRef("pk"))
        
        qs = Order.objects.filter(
            payment_status="paid",
            created_at__lt=grace_period_cutoff,
        ).annotate(
            is_settled=Exists(already_settled)
        ).filter(
            is_settled=False
        )
        
        if store_id:
            qs = qs.filter(store_id=store_id)
        
        orders = []
        for order in qs[:limit]:
            orders.append({
                "order_id": order.id,
                "store_id": order.store_id,
                "total_amount": str(order.total_amount),
                "payment_status": order.payment_status,
                "created_at": order.created_at.isoformat(),
                "hours_since_payment": (timezone.now() - order.created_at).total_seconds() / 3600,
            })
        
        return orders
    
    @staticmethod
    def calculate_settlement_health_score(store_id: int = None) -> Dict:
        """
        Calculate a health score for settlement processing.
        
        Returns score from 0-100 based on:
        - Unsettled orders ratio
        - Average settlement delay
        - Amount discrepancies
        
        Args:
            store_id: Optional store ID to filter by
        
        Returns:
            Dict with health score and metrics
        """
        grace_period_cutoff = timezone.now() - timedelta(hours=24)
        
        # Get total paid orders
        paid_orders_qs = Order.objects.filter(
            payment_status="paid",
            created_at__lt=grace_period_cutoff,
        )
        
        if store_id:
            paid_orders_qs = paid_orders_qs.filter(store_id=store_id)
        
        total_paid = paid_orders_qs.count()
        
        # Get unsettled count
        already_settled = SettlementItem.objects.filter(order_id=OuterRef("pk"))
        unsettled_count = (
            paid_orders_qs
            .annotate(is_settled=Exists(already_settled))
            .filter(is_settled=False)
            .count()
        )
        
        # Calculate metrics
        settlement_rate = (
            ((total_paid - unsettled_count) / total_paid * 100)
            if total_paid > 0
            else 100.0
        )
        
        # Get reconciliation report for last 7 days
        report = ReconciliationService.generate_reconciliation_report(
            lookback_days=7,
            store_id=store_id,
        )
        
        # Calculate health score (weighted)
        health_score = 100.0
        
        # Deduct for unsettled orders (max -30 points)
        if total_paid > 0:
            unsettled_ratio = unsettled_count / total_paid
            health_score -= min(unsettled_ratio * 100, 30)
        
        # Deduct for orphaned items (max -20 points)
        if report.orphaned_settlement_items_count > 0:
            health_score -= min(report.orphaned_settlement_items_count, 20)
        
        # Deduct for amount mismatches (max -30 points)
        if len(report.amount_mismatches) > 0:
            health_score -= min(len(report.amount_mismatches) * 3, 30)
        
        # Deduct for large payment/settlement difference (max -20 points)
        diff_ratio = (
            abs(report.payment_settlement_diff) / report.payment_intents_amount * 100
            if report.payment_intents_amount > 0
            else 0
        )
        health_score -= min(diff_ratio, 20)
        
        health_score = max(health_score, 0)
        
        return {
            "health_score": round(health_score, 2),
            "settlement_rate_percent": round(settlement_rate, 2),
            "total_paid_orders": total_paid,
            "unsettled_orders": unsettled_count,
            "orphaned_items": report.orphaned_settlement_items_count,
            "amount_mismatches": len(report.amount_mismatches),
            "payment_settlement_diff": str(report.payment_settlement_diff),
            "status": _get_health_status(health_score),
        }


def _get_health_status(score: float) -> str:
    """Get health status label from score."""
    if score >= 90:
        return "excellent"
    elif score >= 75:
        return "good"
    elif score >= 60:
        return "fair"
    elif score >= 40:
        return "poor"
    else:
        return "critical"

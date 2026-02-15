from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from orders.models import Order
from tenants.application.dto.merchant_dashboard_metrics import RecentOrderRowDTO
from tenants.application.interfaces.order_repository_port import OrderRepositoryPort


class DjangoOrderRepository(OrderRepositoryPort):
    def sum_sales_today(self, tenant_id: int) -> Decimal:
        now = timezone.now()
        start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return (
            Order.objects.filter(store_id=tenant_id, created_at__gte=start_today)
            .exclude(status__in=["canceled", "cancelled"])
            .aggregate(total=Sum("total_amount"))
            .get("total")
            or Decimal("0.00")
        )

    def count_orders_today(self, tenant_id: int) -> int:
        now = timezone.now()
        start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return (
            Order.objects.filter(store_id=tenant_id, created_at__gte=start_today)
            .exclude(status__in=["canceled", "cancelled"])
            .count()
        )

    def sum_revenue_last_7_days(self, tenant_id: int) -> Decimal:
        now = timezone.now()
        start_7d = now - timedelta(days=7)
        return (
            Order.objects.filter(store_id=tenant_id, created_at__gte=start_7d)
            .exclude(status__in=["canceled", "cancelled"])
            .aggregate(total=Sum("total_amount"))
            .get("total")
            or Decimal("0.00")
        )

    def recent_orders(self, tenant_id: int, limit: int = 10) -> list[RecentOrderRowDTO]:
        rows = (
            Order.objects.filter(store_id=tenant_id)
            .order_by("-created_at")[:limit]
            .values("id", "created_at", "total_amount", "status", "customer_name")
        )
        return [
            RecentOrderRowDTO(
                id=row["id"],
                created_at=row["created_at"],
                total=row["total_amount"],
                status=row["status"],
                customer_name=row["customer_name"] or "",
            )
            for row in rows
        ]
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from analytics.models import Event
from catalog.models import Inventory
from orders.models import Order


@dataclass(frozen=True)
class GetMerchantDashboardMetricsCommand:
    user_id: int
    tenant_id: int
    currency: str = "SAR"
    timezone: str = "UTC"


@dataclass(frozen=True)
class MerchantDashboardMetrics:
    sales_today: Decimal
    orders_today: int
    revenue_7d: Decimal
    visitors_7d: int
    recent_orders: list[dict]
    low_stock: list[dict]


class GetMerchantDashboardMetricsUseCase:
    LOW_STOCK_THRESHOLD = 5

    @staticmethod
    def execute(cmd: GetMerchantDashboardMetricsCommand) -> MerchantDashboardMetrics:
        now = timezone.now()
        start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_7d = now - timedelta(days=7)

        sales_today = (
            Order.objects.filter(
                store_id=cmd.tenant_id,
                created_at__gte=start_today,
            )
            .exclude(status="cancelled")
            .aggregate(total=Sum("total_amount"))
            .get("total")
            or Decimal("0.00")
        )

        orders_today = (
            Order.objects.filter(
                store_id=cmd.tenant_id,
                created_at__gte=start_today,
            )
            .exclude(status="cancelled")
            .count()
        )

        revenue_7d = (
            Order.objects.filter(
                store_id=cmd.tenant_id,
                created_at__gte=start_7d,
            )
            .exclude(status="cancelled")
            .aggregate(total=Sum("total_amount"))
            .get("total")
            or Decimal("0.00")
        )

        visitors_7d = Event.objects.filter(tenant_id=cmd.tenant_id, occurred_at__gte=start_7d).count()

        recent_orders = [
            {
                "id": row["id"],
                "customer_name": row["customer_name"],
                "status": row["status"],
                "total": row["total_amount"],
                "created_at": row["created_at"],
            }
            for row in Order.objects.filter(store_id=cmd.tenant_id)
            .order_by("-created_at")[:10]
            .values("id", "customer_name", "status", "total_amount", "created_at")
        ]

        low_stock = [
            {
                "name": row["product__name"],
                "sku": row["product__sku"],
                "quantity": row["quantity"],
            }
            for row in Inventory.objects.filter(
                product__store_id=cmd.tenant_id,
                product__is_active=True,
                quantity__lte=GetMerchantDashboardMetricsUseCase.LOW_STOCK_THRESHOLD,
            )
            .order_by("quantity", "product__name")[:10]
            .values("product__name", "product__sku", "quantity")
        ]

        return MerchantDashboardMetrics(
            sales_today=sales_today,
            orders_today=orders_today,
            revenue_7d=revenue_7d,
            visitors_7d=visitors_7d,
            recent_orders=recent_orders,
            low_stock=low_stock,
        )

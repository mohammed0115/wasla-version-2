from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import Sum
from django.utils import timezone

from analytics.models import Event
from catalog.models import Inventory
from orders.models import Order


@dataclass(frozen=True)
class RecentOrder:
    id: int
    customer_name: str
    status: str
    total: Decimal
    created_at: Any


@dataclass(frozen=True)
class LowStockItem:
    name: str
    sku: str
    quantity: int


@dataclass(frozen=True)
class MerchantDashboardMetrics:
    sales_today: Decimal
    orders_today: int
    revenue_7d: Decimal
    visitors_7d: int
    recent_orders: list[RecentOrder]
    low_stock: list[LowStockItem]


@dataclass(frozen=True)
class GetMerchantDashboardMetricsCommand:
    user_id: int
    tenant_id: int
    currency: str = "SAR"
    timezone: str | None = None


class GetMerchantDashboardMetricsUseCase:
    LOW_STOCK_THRESHOLD = 5
    LOW_STOCK_LIMIT = 10
    RECENT_ORDERS_LIMIT = 10

    @staticmethod
    def _resolve_tz(tz_name: str | None):
        if not tz_name:
            return timezone.get_current_timezone()
        try:
            return ZoneInfo(str(tz_name))
        except Exception:
            return timezone.get_current_timezone()

    @staticmethod
    def execute(cmd: GetMerchantDashboardMetricsCommand) -> MerchantDashboardMetrics:
        tz = GetMerchantDashboardMetricsUseCase._resolve_tz(cmd.timezone)
        now = timezone.now()
        local_now = timezone.localtime(now, tz)
        start_today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_tomorrow = start_today + timedelta(days=1)
        start_7d = start_today - timedelta(days=6)

        orders_base = Order.objects.filter(store_id=cmd.tenant_id).exclude(status="cancelled")
        orders_today_qs = orders_base.filter(created_at__gte=start_today, created_at__lt=start_tomorrow)

        orders_today = int(orders_today_qs.count())
        sales_today = orders_today_qs.aggregate(total=Sum("total_amount")).get("total") or Decimal("0")
        revenue_7d = (
            orders_base.filter(created_at__gte=start_7d, created_at__lt=start_tomorrow)
            .aggregate(total=Sum("total_amount"))
            .get("total")
            or Decimal("0")
        )

        recent_orders: list[RecentOrder] = []
        recent_orders_qs = (
            Order.objects.filter(store_id=cmd.tenant_id)
            .select_related("customer")
            .order_by("-created_at")[: GetMerchantDashboardMetricsUseCase.RECENT_ORDERS_LIMIT]
        )
        for order in recent_orders_qs:
            customer_name = (getattr(order, "customer_name", "") or "").strip()
            if not customer_name and getattr(order, "customer", None) is not None:
                customer_name = (
                    (getattr(order.customer, "full_name", "") or "").strip()
                    or (getattr(order.customer, "email", "") or "").strip()
                )
            recent_orders.append(
                RecentOrder(
                    id=int(order.id),
                    customer_name=customer_name,
                    status=str(getattr(order, "status", "") or ""),
                    total=getattr(order, "total_amount", None) or Decimal("0"),
                    created_at=getattr(order, "created_at", None),
                )
            )

        low_stock: list[LowStockItem] = []
        low_stock_qs = (
            Inventory.objects.select_related("product")
            .filter(product__store_id=cmd.tenant_id, quantity__lte=GetMerchantDashboardMetricsUseCase.LOW_STOCK_THRESHOLD)
            .order_by("quantity")[: GetMerchantDashboardMetricsUseCase.LOW_STOCK_LIMIT]
        )
        for inv in low_stock_qs:
            product = getattr(inv, "product", None)
            if product is None:
                continue
            low_stock.append(
                LowStockItem(
                    name=str(getattr(product, "name", "") or ""),
                    sku=str(getattr(product, "sku", "") or ""),
                    quantity=int(getattr(inv, "quantity", 0) or 0),
                )
            )

        visitors_7d = 0
        try:
            visitors_7d = int(
                Event.objects.filter(
                    tenant_id=cmd.tenant_id,
                    actor_type__in=[Event.ACTOR_ANON, Event.ACTOR_CUSTOMER],
                    occurred_at__gte=start_7d,
                    occurred_at__lt=start_tomorrow,
                )
                .exclude(session_key_hash="")
                .values("session_key_hash")
                .distinct()
                .count()
            )
        except Exception:
            visitors_7d = 0

        return MerchantDashboardMetrics(
            sales_today=sales_today,
            orders_today=orders_today,
            revenue_7d=revenue_7d,
            visitors_7d=visitors_7d,
            recent_orders=recent_orders,
            low_stock=low_stock,
        )

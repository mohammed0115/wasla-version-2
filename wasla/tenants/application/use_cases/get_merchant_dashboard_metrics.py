from __future__ import annotations

from dataclasses import dataclass
<<<<<<< HEAD
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
=======
from decimal import Decimal

from tenants.application.dto.merchant_dashboard_metrics import (
    GetMerchantDashboardMetricsQuery,
    MerchantDashboardMetricsDTO,
)
from tenants.application.interfaces.order_repository_port import OrderRepositoryPort
from tenants.application.interfaces.visitor_repository_port import VisitorRepositoryPort
from tenants.infrastructure.repositories.django_order_repository import DjangoOrderRepository
from tenants.infrastructure.repositories.django_visitor_repository import DjangoVisitorRepository
>>>>>>> 832f5c3e885d0444fc716cb968d915a3e44d23a9


@dataclass(frozen=True)
class GetMerchantDashboardMetricsCommand:
    user_id: int
    tenant_id: int
    currency: str = "SAR"
<<<<<<< HEAD
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
=======
    timezone: str = "UTC"


MerchantDashboardMetrics = MerchantDashboardMetricsDTO


class GetMerchantDashboardMetricsUseCase:
    def __init__(
        self,
        order_repository: OrderRepositoryPort | None = None,
        visitor_repository: VisitorRepositoryPort | None = None,
    ) -> None:
        self._order_repository = order_repository or DjangoOrderRepository()
        self._visitor_repository = visitor_repository or DjangoVisitorRepository()

    def execute(
        self,
        query: GetMerchantDashboardMetricsQuery | GetMerchantDashboardMetricsCommand,
    ) -> MerchantDashboardMetricsDTO:
        normalized_query = self._normalize_query(query)

        sales_today = self._order_repository.sum_sales_today(normalized_query.tenant_id)
        orders_today = self._order_repository.count_orders_today(normalized_query.tenant_id)
        revenue_7d = self._order_repository.sum_revenue_last_7_days(normalized_query.tenant_id)
        visitors_7d = self._visitor_repository.count_visitors_last_7_days(normalized_query.tenant_id)
        recent_orders = self._order_repository.recent_orders(normalized_query.tenant_id, limit=10)

        conversion_7d = (
            Decimal("0")
            if visitors_7d == 0
            else Decimal(orders_today) / Decimal(visitors_7d)
        )

        return MerchantDashboardMetricsDTO(
>>>>>>> 832f5c3e885d0444fc716cb968d915a3e44d23a9
            sales_today=sales_today,
            orders_today=orders_today,
            revenue_7d=revenue_7d,
            visitors_7d=visitors_7d,
<<<<<<< HEAD
            recent_orders=recent_orders,
            low_stock=low_stock,
=======
            conversion_7d=conversion_7d,
            recent_orders=recent_orders,
        )

    @classmethod
    def execute_default(
        cls,
        query: GetMerchantDashboardMetricsQuery | GetMerchantDashboardMetricsCommand,
    ) -> MerchantDashboardMetricsDTO:
        return cls().execute(query)

    @staticmethod
    def _normalize_query(
        query: GetMerchantDashboardMetricsQuery | GetMerchantDashboardMetricsCommand,
    ) -> GetMerchantDashboardMetricsQuery:
        if isinstance(query, GetMerchantDashboardMetricsQuery):
            return query

        return GetMerchantDashboardMetricsQuery(
            actor_user_id=query.user_id,
            tenant_id=query.tenant_id,
            currency=query.currency,
            timezone=query.timezone,
>>>>>>> 832f5c3e885d0444fc716cb968d915a3e44d23a9
        )

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from apps.tenants.application.dto.merchant_dashboard_metrics import (
    ChartPointDTO,
    GetMerchantDashboardMetricsQuery,
    MerchantDashboardMetricsDTO,
)
from apps.tenants.application.interfaces.inventory_repository_port import InventoryRepositoryPort
from apps.tenants.application.interfaces.order_repository_port import OrderRepositoryPort
from apps.tenants.application.interfaces.visitor_repository_port import VisitorRepositoryPort
from apps.tenants.infrastructure.repositories.django_low_stock_repository import DjangoLowStockRepository
from apps.tenants.infrastructure.repositories.django_order_repository import DjangoOrderRepository
from apps.tenants.infrastructure.repositories.django_visitor_repository import DjangoVisitorRepository


@dataclass(frozen=True)
class GetMerchantDashboardMetricsCommand:
    user_id: int
    store_id: int
    currency: str = "SAR"
    timezone: str = "UTC"


MerchantDashboardMetrics = MerchantDashboardMetricsDTO


class GetMerchantDashboardMetricsUseCase:
    def __init__(
        self,
        order_repository: OrderRepositoryPort | None = None,
        visitor_repository: VisitorRepositoryPort | None = None,
        inventory_repository: InventoryRepositoryPort | None = None,
    ) -> None:
        self._order_repository = order_repository or DjangoOrderRepository()
        self._visitor_repository = visitor_repository or DjangoVisitorRepository()
        self._inventory_repository = inventory_repository or DjangoLowStockRepository()

    def execute(
        self,
        query: GetMerchantDashboardMetricsQuery | GetMerchantDashboardMetricsCommand,
    ) -> MerchantDashboardMetricsDTO:
        normalized_query = self._normalize_query(query)

        sales_today = self._order_repository.sum_sales_today(
            store_id=normalized_query.store_id,
            tz=normalized_query.timezone,
        )
        orders_today = self._order_repository.count_orders_today(
            store_id=normalized_query.store_id,
            tz=normalized_query.timezone,
        )
        revenue_7d = self._order_repository.sum_revenue_last_7_days(
            store_id=normalized_query.store_id,
            tz=normalized_query.timezone,
        )
        visitors_7d = self._visitor_repository.count_visitors_last_7_days(
            store_id=normalized_query.store_id,
            tz=normalized_query.timezone,
        )
        raw_chart_7d = self._order_repository.chart_revenue_orders_last_7_days(
            store_id=normalized_query.store_id,
            tz=normalized_query.timezone,
        )
        recent_orders = self._order_repository.recent_orders(normalized_query.store_id, limit=10)
        low_stock = self._inventory_repository.low_stock_products(normalized_query.store_id, threshold=5, limit=10)

        chart_7d = self._with_revenue_levels(raw_chart_7d)
        orders_7d = sum(int(point["orders"]) for point in chart_7d)

        conversion_7d = (
            Decimal("0")
            if visitors_7d == 0
            else Decimal(orders_7d) / Decimal(visitors_7d)
        )

        return MerchantDashboardMetricsDTO(
            sales_today=sales_today,
            orders_today=orders_today,
            revenue_7d=revenue_7d,
            visitors_7d=visitors_7d,
            conversion_7d=conversion_7d,
            chart_7d=chart_7d,
            recent_orders=recent_orders,
            low_stock=low_stock,
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
            store_id=query.store_id,
            currency=query.currency,
            timezone=query.timezone,
        )

    @staticmethod
    def _with_revenue_levels(chart_7d: list[ChartPointDTO]) -> list[ChartPointDTO]:
        if not chart_7d:
            return []

        max_revenue = max((Decimal(point["revenue"]) for point in chart_7d), default=Decimal("0"))
        if max_revenue <= Decimal("0"):
            return [
                {
                    "date": point["date"],
                    "revenue": Decimal(point["revenue"]),
                    "orders": int(point["orders"]),
                    "revenue_level": 0,
                }
                for point in chart_7d
            ]

        normalized: list[ChartPointDTO] = []
        for point in chart_7d:
            revenue = Decimal(point["revenue"])
            if revenue <= Decimal("0"):
                level = 0
            else:
                level = int(((revenue / max_revenue) * Decimal("10")).to_integral_value(rounding=ROUND_HALF_UP))
                level = max(0, min(10, level))
            normalized.append(
                {
                    "date": point["date"],
                    "revenue": revenue,
                    "orders": int(point["orders"]),
                    "revenue_level": level,
                }
            )
        return normalized

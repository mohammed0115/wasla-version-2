from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from tenants.application.dto.merchant_dashboard_metrics import (
    GetMerchantDashboardMetricsQuery,
    MerchantDashboardMetricsDTO,
)
from tenants.application.interfaces.order_repository_port import OrderRepositoryPort
from tenants.application.interfaces.visitor_repository_port import VisitorRepositoryPort
from tenants.infrastructure.repositories.django_order_repository import DjangoOrderRepository
from tenants.infrastructure.repositories.django_visitor_repository import DjangoVisitorRepository


@dataclass(frozen=True)
class GetMerchantDashboardMetricsCommand:
    user_id: int
    tenant_id: int
    currency: str = "SAR"
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
            sales_today=sales_today,
            orders_today=orders_today,
            revenue_7d=revenue_7d,
            visitors_7d=visitors_7d,
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
        )

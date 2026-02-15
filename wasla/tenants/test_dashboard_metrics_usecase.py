from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone as dt_timezone

from django.test import SimpleTestCase

from tenants.application.dto.merchant_dashboard_metrics import (
    GetMerchantDashboardMetricsQuery,
    RecentOrderRowDTO,
)
from tenants.application.use_cases.get_merchant_dashboard_metrics import (
    GetMerchantDashboardMetricsUseCase,
)


class _FakeOrderRepository:
    def sum_sales_today(self, tenant_id: int) -> Decimal:
        return Decimal("150.00")

    def count_orders_today(self, tenant_id: int) -> int:
        return 3

    def sum_revenue_last_7_days(self, tenant_id: int) -> Decimal:
        return Decimal("700.00")

    def recent_orders(self, tenant_id: int, limit: int = 10) -> list[RecentOrderRowDTO]:
        return [
            RecentOrderRowDTO(
                id=1,
                created_at=datetime(2026, 2, 15, 10, 0, tzinfo=dt_timezone.utc),
                total=Decimal("50.00"),
                status="paid",
                customer_name="Alice",
            )
        ]


class _FakeVisitorRepository:
    def __init__(self, visitors_7d: int) -> None:
        self.visitors_7d = visitors_7d

    def count_visitors_last_7_days(self, tenant_id: int) -> int:
        return self.visitors_7d


class DashboardMetricsUseCaseTests(SimpleTestCase):
    def test_execute_computes_conversion_when_visitors_exist(self):
        use_case = GetMerchantDashboardMetricsUseCase(
            order_repository=_FakeOrderRepository(),
            visitor_repository=_FakeVisitorRepository(visitors_7d=12),
        )

        result = use_case.execute(
            GetMerchantDashboardMetricsQuery(
                actor_user_id=10,
                tenant_id=1,
                currency="SAR",
                timezone="UTC",
            )
        )

        self.assertEqual(result.sales_today, Decimal("150.00"))
        self.assertEqual(result.orders_today, 3)
        self.assertEqual(result.revenue_7d, Decimal("700.00"))
        self.assertEqual(result.visitors_7d, 12)
        self.assertEqual(result.conversion_7d, Decimal("0.25"))
        self.assertEqual(len(result.recent_orders), 1)

    def test_execute_returns_zero_conversion_when_no_visitors(self):
        use_case = GetMerchantDashboardMetricsUseCase(
            order_repository=_FakeOrderRepository(),
            visitor_repository=_FakeVisitorRepository(visitors_7d=0),
        )

        result = use_case.execute(
            GetMerchantDashboardMetricsQuery(
                actor_user_id=10,
                tenant_id=1,
                currency="SAR",
                timezone="UTC",
            )
        )

        self.assertEqual(result.conversion_7d, Decimal("0"))

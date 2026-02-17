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
    def sum_sales_today(self, store_id: int, tz: str) -> Decimal:
        return Decimal("150.00")

    def count_orders_today(self, store_id: int, tz: str) -> int:
        return 3

    def sum_revenue_last_7_days(self, store_id: int, tz: str) -> Decimal:
        return Decimal("700.00")

    def chart_revenue_orders_last_7_days(self, store_id: int, tz: str) -> list[dict]:
        return [
            {"date": "2026-02-09", "revenue": Decimal("50.00"), "orders": 1, "revenue_level": 0},
            {"date": "2026-02-10", "revenue": Decimal("150.00"), "orders": 2, "revenue_level": 0},
            {"date": "2026-02-11", "revenue": Decimal("0.00"), "orders": 0, "revenue_level": 0},
            {"date": "2026-02-12", "revenue": Decimal("200.00"), "orders": 3, "revenue_level": 0},
            {"date": "2026-02-13", "revenue": Decimal("100.00"), "orders": 1, "revenue_level": 0},
            {"date": "2026-02-14", "revenue": Decimal("100.00"), "orders": 2, "revenue_level": 0},
            {"date": "2026-02-15", "revenue": Decimal("100.00"), "orders": 1, "revenue_level": 0},
        ]

    def recent_orders(self, store_id: int, limit: int = 10) -> list[RecentOrderRowDTO]:
        return [
            {
                "id": 1,
                "created_at": datetime(2026, 2, 15, 10, 0, tzinfo=dt_timezone.utc),
                "total": Decimal("50.00"),
                "status": "paid",
                "customer_name": "Alice",
            }
        ]


class _FakeInventoryRepository:
    def low_stock_products(self, store_id: int, threshold: int = 5, limit: int = 10) -> list[dict]:
        return [{"product_id": 1, "name": "P1", "sku": "SKU1", "quantity": 2}]


class _FakeVisitorRepository:
    def __init__(self, visitors_7d: int) -> None:
        self.visitors_7d = visitors_7d

    def count_visitors_last_7_days(self, store_id: int, tz: str) -> int:
        return self.visitors_7d


class DashboardMetricsUseCaseTests(SimpleTestCase):
    def test_execute_computes_conversion_when_visitors_exist(self):
        use_case = GetMerchantDashboardMetricsUseCase(
            order_repository=_FakeOrderRepository(),
            visitor_repository=_FakeVisitorRepository(visitors_7d=12),
            inventory_repository=_FakeInventoryRepository(),
        )

        result = use_case.execute(
            GetMerchantDashboardMetricsQuery(
                actor_user_id=10,
                store_id=1,
                currency="SAR",
                timezone="UTC",
            )
        )

        self.assertEqual(result.sales_today, Decimal("150.00"))
        self.assertEqual(result.orders_today, 3)
        self.assertEqual(result.revenue_7d, Decimal("700.00"))
        self.assertEqual(result.visitors_7d, 12)
        self.assertEqual(result.conversion_7d, Decimal("0.8333333333333333333333333333"))
        self.assertEqual(len(result.chart_7d), 7)
        self.assertEqual(len(result.recent_orders), 1)
        self.assertEqual(len(result.low_stock), 1)

    def test_execute_returns_zero_conversion_when_no_visitors(self):
        use_case = GetMerchantDashboardMetricsUseCase(
            order_repository=_FakeOrderRepository(),
            visitor_repository=_FakeVisitorRepository(visitors_7d=0),
            inventory_repository=_FakeInventoryRepository(),
        )

        result = use_case.execute(
            GetMerchantDashboardMetricsQuery(
                actor_user_id=10,
                store_id=1,
                currency="SAR",
                timezone="UTC",
            )
        )

        self.assertEqual(result.conversion_7d, Decimal("0"))

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from tenants.application.dto.merchant_dashboard_metrics import ChartPointDTO, RecentOrderRowDTO


class OrderRepositoryPort(Protocol):
    def sum_sales_today(self, store_id: int, tz: str) -> Decimal:
        ...

    def count_orders_today(self, store_id: int, tz: str) -> int:
        ...

    def sum_revenue_last_7_days(self, store_id: int, tz: str) -> Decimal:
        ...

    def chart_revenue_orders_last_7_days(self, store_id: int, tz: str) -> list[ChartPointDTO]:
        ...

    def recent_orders(self, store_id: int, limit: int = 10) -> list[RecentOrderRowDTO]:
        ...

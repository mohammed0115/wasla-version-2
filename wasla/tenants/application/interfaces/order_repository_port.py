from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from tenants.application.dto.merchant_dashboard_metrics import RecentOrderRowDTO


class OrderRepositoryPort(Protocol):
    def sum_sales_today(self, tenant_id: int) -> Decimal:
        ...

    def count_orders_today(self, tenant_id: int) -> int:
        ...

    def sum_revenue_last_7_days(self, tenant_id: int) -> Decimal:
        ...

    def recent_orders(self, tenant_id: int, limit: int = 10) -> list[RecentOrderRowDTO]:
        ...
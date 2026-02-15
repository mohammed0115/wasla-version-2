from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class GetMerchantDashboardMetricsQuery:
    actor_user_id: int
    tenant_id: int
    currency: str
    timezone: str


@dataclass(frozen=True)
class RecentOrderRowDTO:
    id: int
    created_at: datetime
    total: Decimal
    status: str
    customer_name: str


@dataclass(frozen=True)
class MerchantDashboardMetricsDTO:
    sales_today: Decimal
    orders_today: int
    revenue_7d: Decimal
    visitors_7d: int
    conversion_7d: Decimal
    recent_orders: list[RecentOrderRowDTO]
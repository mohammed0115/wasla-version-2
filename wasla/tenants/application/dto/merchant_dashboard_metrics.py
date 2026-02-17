from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TypedDict


@dataclass(frozen=True)
class GetMerchantDashboardMetricsQuery:
    actor_user_id: int
    tenant_id: int
    currency: str
    timezone: str


class ChartPointDTO(TypedDict):
    date: str
    revenue: Decimal
    orders: int
    revenue_level: int


class RecentOrderRowDTO(TypedDict):
    id: int
    created_at: datetime
    total: Decimal
    status: str
    customer_name: str


class LowStockRowDTO(TypedDict):
    product_id: int
    name: str
    sku: str
    quantity: int


@dataclass(frozen=True)
class MerchantDashboardMetricsDTO:
    sales_today: Decimal
    orders_today: int
    revenue_7d: Decimal
    visitors_7d: int
    conversion_7d: Decimal
    chart_7d: list[ChartPointDTO]
    recent_orders: list[RecentOrderRowDTO]
    low_stock: list[LowStockRowDTO]
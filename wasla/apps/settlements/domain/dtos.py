from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True)
class BalanceSummary:
    currency: str
    available_balance: Decimal
    pending_balance: Decimal


@dataclass(frozen=True)
class SettlementSummary:
    id: int
    period_start: date
    period_end: date
    gross_amount: Decimal
    fees_amount: Decimal
    net_amount: Decimal
    status: str
    created_at: datetime | None = None
    approved_at: datetime | None = None
    paid_at: datetime | None = None


@dataclass(frozen=True)
class SettlementDetail:
    settlement: SettlementSummary
    items: Sequence[dict]

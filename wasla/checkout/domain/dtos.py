from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ShippingMethodDTO:
    code: str
    label: str
    fee: Decimal


@dataclass(frozen=True)
class CheckoutSummary:
    session_id: int
    status: str
    totals: Mapping[str, Decimal]
    shipping_methods: Sequence[ShippingMethodDTO]

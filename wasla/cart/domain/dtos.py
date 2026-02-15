from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True)
class CartItemDTO:
    id: int
    product_id: int
    name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class CartSummary:
    cart_id: int | None
    currency: str
    items: Sequence[CartItemDTO]
    subtotal: Decimal
    total: Decimal

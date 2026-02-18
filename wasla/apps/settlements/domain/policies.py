from __future__ import annotations

from decimal import Decimal


def ensure_non_negative_amount(amount: Decimal, field: str = "amount") -> Decimal:
    value = Decimal(str(amount or "0"))
    if value < 0:
        raise ValueError(f"{field} must be non-negative.")
    return value


def ensure_positive_amount(amount: Decimal, field: str = "amount") -> Decimal:
    value = Decimal(str(amount or "0"))
    if value <= 0:
        raise ValueError(f"{field} must be positive.")
    return value

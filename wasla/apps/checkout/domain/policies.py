from __future__ import annotations

from decimal import Decimal

from apps.checkout.domain.errors import InvalidAddressError


REQUIRED_ADDRESS_FIELDS = ("full_name", "email", "phone", "line1", "city", "country")


def validate_address(address: dict) -> dict:
    cleaned = {k: (address.get(k) or "").strip() for k in REQUIRED_ADDRESS_FIELDS}
    missing = [k for k, v in cleaned.items() if not v]
    if missing:
        raise InvalidAddressError(f"Missing required fields: {', '.join(missing)}")
    return cleaned


def compute_totals(*, subtotal: Decimal, shipping_fee: Decimal) -> dict:
    subtotal = Decimal(subtotal or "0")
    shipping_fee = Decimal(shipping_fee or "0")
    total = subtotal + shipping_fee
    if total < 0:
        total = Decimal("0")
    return {"subtotal": subtotal, "shipping_fee": shipping_fee, "total": total}

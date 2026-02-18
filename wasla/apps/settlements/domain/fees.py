from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from apps.subscriptions.services.subscription_service import SubscriptionService


@dataclass(frozen=True)
class FeePolicy:
    percent: Decimal
    flat: Decimal


def _to_decimal(value) -> Decimal:
    return Decimal(str(value or "0"))


def resolve_fee_policy(store_id: int) -> FeePolicy:
    """
    Resolve settlement fee policy from the active subscription plan (if any).
    Supports:
    - features as dict with settlement_fee_percent / settlement_fee_flat
    - features as list of dicts with same keys
    """
    percent = Decimal("0")
    flat = Decimal("0")

    subscription = SubscriptionService.get_active_subscription(store_id)
    plan = getattr(subscription, "plan", None)
    features = getattr(plan, "features", None) if plan else None

    if isinstance(features, dict):
        percent = _to_decimal(features.get("settlement_fee_percent") or percent)
        flat = _to_decimal(features.get("settlement_fee_flat") or flat)
    elif isinstance(features, list):
        for item in features:
            if not isinstance(item, dict):
                continue
            if "settlement_fee_percent" in item:
                percent = _to_decimal(item.get("settlement_fee_percent"))
            if "settlement_fee_flat" in item:
                flat = _to_decimal(item.get("settlement_fee_flat"))

    if percent < 0:
        percent = Decimal("0")
    if flat < 0:
        flat = Decimal("0")

    return FeePolicy(percent=percent, flat=flat)


def allocate_fees(order_amounts: Iterable[Decimal], *, policy: FeePolicy) -> list[Decimal]:
    """
    Allocate fees across orders.
    - Percent fee per order.
    - Flat fee distributed proportionally across orders.
    """
    amounts = [Decimal(str(a)) for a in order_amounts]
    if not amounts:
        return []

    total = sum(amounts)
    percent_rate = policy.percent / Decimal("100") if policy.percent else Decimal("0")
    percent_fees = [(_to_decimal(a) * percent_rate) for a in amounts]

    flat_total = _to_decimal(policy.flat)
    if total <= 0 or flat_total <= 0:
        return [_round_fee(f) for f in percent_fees]

    flat_shares = []
    allocated = Decimal("0")
    for idx, amount in enumerate(amounts):
        if idx == len(amounts) - 1:
            share = flat_total - allocated
        else:
            share = (amount / total) * flat_total
            share = _round_fee(share)
            allocated += share
        flat_shares.append(share)

    return [_round_fee(p + f) for p, f in zip(percent_fees, flat_shares)]


def _round_fee(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

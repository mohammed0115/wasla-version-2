from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import timedelta

from django.db.models import Avg
from django.utils import timezone

from apps.analytics.domain.types import RiskScoreDTO
from apps.analytics.models import Event
from apps.orders.models import Order
from apps.payments.models import PaymentIntent


@dataclass(frozen=True)
class FraudRuleResult:
    score: int
    reasons: list[str]


def evaluate_fraud_rules(*, tenant_id: int, order: Order) -> FraudRuleResult:
    score = 0
    reasons: list[str] = []

    avg_amount = (
        Order.objects.filter(store_id=tenant_id)
        .exclude(id=order.id)
        .aggregate(avg_amount=Avg("total_amount"))
        .get("avg_amount")
    )
    if avg_amount and order.total_amount > (Decimal(str(avg_amount)) * Decimal("3")):
        score += 40
        reasons.append("high_order_amount")

    recent_failed = PaymentIntent.objects.filter(
        store_id=tenant_id,
        status="failed",
        created_at__gte=timezone.now() - timedelta(minutes=15),
    ).count()
    if recent_failed >= 3:
        score += 25
        reasons.append("many_failed_payments")

    ip_hash = Event.objects.filter(
        tenant_id=tenant_id,
        event_name="order.placed",
        object_id=str(order.id),
    ).values_list("ip_hash", flat=True).first()
    if ip_hash:
        recent_same_ip = Event.objects.filter(
            tenant_id=tenant_id,
            event_name="order.placed",
            ip_hash=ip_hash,
            occurred_at__gte=timezone.now() - timedelta(minutes=10),
        ).count()
        if recent_same_ip >= 3:
            score += 20
            reasons.append("multiple_orders_same_ip")

    score = min(score, 100)
    return FraudRuleResult(score=score, reasons=reasons)


def score_to_level(score: int) -> str:
    if score >= 70:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"

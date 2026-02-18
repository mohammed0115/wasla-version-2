from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.analytics.domain.types import RiskScoreDTO
from apps.analytics.infrastructure.rules.fraud_rules import evaluate_fraud_rules, score_to_level
from apps.analytics.models import RiskAssessment
from apps.orders.models import Order
from apps.tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class ScoreTransactionCommand:
    tenant_ctx: TenantContext
    order_id: int


class ScoreTransactionUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: ScoreTransactionCommand) -> RiskScoreDTO:
        existing = RiskAssessment.objects.select_for_update().filter(
            tenant_id=cmd.tenant_ctx.tenant_id, order_id=cmd.order_id
        ).first()
        if existing:
            return RiskScoreDTO(
                order_id=existing.order_id,
                score=existing.score,
                level=existing.level,
                reasons=list(existing.reasons_json or []),
            )

        order = Order.objects.filter(id=cmd.order_id, store_id=cmd.tenant_ctx.tenant_id).first()
        if not order:
            raise ValueError("Order not found.")

        result = evaluate_fraud_rules(tenant_id=cmd.tenant_ctx.tenant_id, order=order)
        level = score_to_level(result.score)
        assessment = RiskAssessment.objects.create(
            tenant_id=cmd.tenant_ctx.tenant_id,
            order_id=order.id,
            score=result.score,
            level=level,
            reasons_json=result.reasons,
        )
        return RiskScoreDTO(
            order_id=assessment.order_id,
            score=assessment.score,
            level=assessment.level,
            reasons=list(assessment.reasons_json or []),
        )

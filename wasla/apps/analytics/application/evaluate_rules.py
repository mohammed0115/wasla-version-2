from __future__ import annotations

from dataclasses import dataclass

from apps.analytics.domain.types import RiskScoreDTO
from apps.analytics.infrastructure.rules.fraud_rules import evaluate_fraud_rules, score_to_level
from apps.orders.models import Order
from apps.tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class EvaluateRulesCommand:
    tenant_ctx: TenantContext
    order_id: int


class EvaluateRulesUseCase:
    @staticmethod
    def execute(cmd: EvaluateRulesCommand) -> RiskScoreDTO | None:
        order = Order.objects.filter(id=cmd.order_id, store_id=cmd.tenant_ctx.tenant_id).first()
        if not order:
            return None
        result = evaluate_fraud_rules(tenant_id=cmd.tenant_ctx.tenant_id, order=order)
        level = score_to_level(result.score)
        return RiskScoreDTO(order_id=order.id, score=result.score, level=level, reasons=result.reasons)

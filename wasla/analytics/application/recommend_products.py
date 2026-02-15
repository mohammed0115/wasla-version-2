from __future__ import annotations

from dataclasses import dataclass

from analytics.infrastructure.rules.recommendation_rules import (
    recommend_for_cart,
    recommend_for_home,
    recommend_for_product,
)
from analytics.models import RecommendationSnapshot
from tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class RecommendProductsCommand:
    tenant_ctx: TenantContext
    context: str
    object_id: str | int | None = None


class RecommendProductsUseCase:
    @staticmethod
    def execute(cmd: RecommendProductsCommand) -> RecommendationSnapshot:
        context = (cmd.context or "").upper()
        tenant_id = cmd.tenant_ctx.tenant_id
        object_id = cmd.object_id

        recommended: list[int] = []
        if context == "PRODUCT_DETAIL" and object_id:
            recommended = recommend_for_product(tenant_id=tenant_id, product_id=int(object_id))
        elif context == "CART" and object_id:
            recommended = recommend_for_cart(tenant_id=tenant_id, cart_id=int(object_id))
        else:
            recommended = recommend_for_home(tenant_id=tenant_id)

        return RecommendationSnapshot.objects.create(
            tenant_id=tenant_id,
            context=context,
            object_id=str(object_id) if object_id is not None else "",
            recommended_ids_json=recommended,
            strategy=RecommendationSnapshot.STRATEGY_RULES_V1,
        )

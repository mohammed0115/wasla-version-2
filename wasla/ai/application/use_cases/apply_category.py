from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from catalog.models import Category, Product
from tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class ApplyCategoryCommand:
    tenant_ctx: TenantContext
    actor_id: int | None
    product_id: int
    category_id: int


class ApplyCategoryUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: ApplyCategoryCommand) -> bool:
        product = Product.objects.select_for_update().filter(
            id=cmd.product_id, store_id=cmd.tenant_ctx.tenant_id
        ).first()
        if not product:
            return False
        category = Category.objects.filter(id=cmd.category_id, store_id=cmd.tenant_ctx.tenant_id).first()
        if not category:
            return False
        product.categories.add(category)
        return True

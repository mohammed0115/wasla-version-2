from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.catalog.models import Product
from apps.tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class SaveProductDescriptionCommand:
    tenant_ctx: TenantContext
    actor_id: int | None
    product_id: int
    language: str
    description: str
    force: bool = False


@dataclass(frozen=True)
class SaveProductDescriptionResult:
    product: Product | None
    saved: bool
    reason: str | None = None


class SaveProductDescriptionUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: SaveProductDescriptionCommand) -> SaveProductDescriptionResult:
        product = Product.objects.select_for_update().filter(
            id=cmd.product_id, store_id=cmd.tenant_ctx.store_id
        ).first()
        if not product:
            return SaveProductDescriptionResult(product=None, saved=False, reason="product_not_found")
        text = (cmd.description or "").strip()
        if cmd.language == "en":
            if product.description_en and not cmd.force:
                return SaveProductDescriptionResult(product=product, saved=False, reason="already_exists")
            product.description_en = text
        else:
            if product.description_ar and not cmd.force:
                return SaveProductDescriptionResult(product=product, saved=False, reason="already_exists")
            product.description_ar = text
        product.save(update_fields=["description_ar", "description_en"])
        return SaveProductDescriptionResult(product=product, saved=True, reason=None)

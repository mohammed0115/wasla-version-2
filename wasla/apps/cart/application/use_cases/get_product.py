from __future__ import annotations

from dataclasses import dataclass

from apps.catalog.models import Product
from apps.tenants.domain.tenant_context import TenantContext
from apps.analytics.application.telemetry import TelemetryService, actor_from_tenant_ctx
from apps.analytics.domain.types import ObjectRef
from core.infrastructure.store_cache import StoreCacheService


@dataclass(frozen=True)
class GetProductCommand:
    tenant_ctx: TenantContext
    product_id: int


class GetProductUseCase:
    @staticmethod
    def execute(cmd: GetProductCommand) -> Product:
        def _load_product() -> Product | None:
            return Product.objects.filter(
                id=cmd.product_id,
                store_id=cmd.tenant_ctx.store_id,
                is_active=True,
            ).first()

        product, _ = StoreCacheService.get_or_set(
            store_id=cmd.tenant_ctx.store_id,
            namespace="product_detail",
            key_parts=[cmd.product_id],
            producer=_load_product,
            timeout=180,
        )
        if not product:
            raise ValueError("Product not found.")
        TelemetryService.track(
            event_name="product.viewed",
            tenant_ctx=cmd.tenant_ctx,
            actor_ctx=actor_from_tenant_ctx(tenant_ctx=cmd.tenant_ctx, actor_type="CUSTOMER"),
            object_ref=ObjectRef(object_type="PRODUCT", object_id=product.id),
            properties={"sku": product.sku},
        )
        return product

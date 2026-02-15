from __future__ import annotations

from dataclasses import dataclass

from catalog.models import Product
from tenants.domain.tenant_context import TenantContext
from analytics.application.telemetry import TelemetryService, actor_from_tenant_ctx
from analytics.domain.types import ObjectRef


@dataclass(frozen=True)
class GetProductCommand:
    tenant_ctx: TenantContext
    product_id: int


class GetProductUseCase:
    @staticmethod
    def execute(cmd: GetProductCommand) -> Product:
        product = Product.objects.filter(
            id=cmd.product_id,
            store_id=cmd.tenant_ctx.tenant_id,
            is_active=True,
        ).first()
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

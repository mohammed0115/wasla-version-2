from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from cart.domain.errors import CartNotFoundError
from cart.domain.policies import assert_cart_access
from cart.infrastructure.repositories import find_cart
from tenants.domain.tenant_context import TenantContext
from analytics.application.telemetry import TelemetryService, actor_from_tenant_ctx
from analytics.domain.types import ObjectRef

from .get_cart import GetCartUseCase


@dataclass(frozen=True)
class RemoveCartItemCommand:
    tenant_ctx: TenantContext
    item_id: int


class RemoveCartItemUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: RemoveCartItemCommand):
        cart = find_cart(cmd.tenant_ctx)
        if not cart:
            raise CartNotFoundError("Cart not found.")
        assert_cart_access(cart, cmd.tenant_ctx)

        item = cart.items.filter(id=cmd.item_id).first()
        if not item:
            raise CartNotFoundError("Cart item not found.")
        TelemetryService.track(
            event_name="cart.item_removed",
            tenant_ctx=cmd.tenant_ctx,
            actor_ctx=actor_from_tenant_ctx(tenant_ctx=cmd.tenant_ctx, actor_type="CUSTOMER"),
            object_ref=ObjectRef(object_type="PRODUCT", object_id=item.product_id),
            properties={"quantity": item.quantity},
        )
        item.delete()
        return GetCartUseCase.execute(cmd.tenant_ctx)

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.cart.domain.dtos import CartSummary
from apps.cart.domain.errors import CartError
from apps.cart.domain.policies import ensure_positive_quantity
from apps.cart.infrastructure.repositories import get_or_create_cart
from apps.catalog.models import Product
from apps.tenants.domain.tenant_context import TenantContext
from apps.analytics.application.telemetry import TelemetryService, actor_from_tenant_ctx
from apps.analytics.domain.types import ObjectRef

from .get_cart import GetCartUseCase


@dataclass(frozen=True)
class AddToCartCommand:
    tenant_ctx: TenantContext
    product_id: int
    quantity: int


class AddToCartUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: AddToCartCommand) -> CartSummary:
        quantity = ensure_positive_quantity(cmd.quantity)
        product = Product.objects.filter(
            id=cmd.product_id,
            store_id=cmd.tenant_ctx.tenant_id,
            is_active=True,
        ).first()
        if not product:
            raise CartError("Product not found.")

        cart = get_or_create_cart(cmd.tenant_ctx)
        item = cart.items.filter(product_id=product.id).first()
        if item:
            item.quantity = item.quantity + quantity
            item.unit_price_snapshot = product.price
            item.save(update_fields=["quantity", "unit_price_snapshot"])
        else:
            cart.items.create(
                product=product,
                quantity=quantity,
                unit_price_snapshot=product.price,
            )
        cart.currency = cmd.tenant_ctx.currency or cart.currency
        cart.save(update_fields=["currency", "updated_at"])
        TelemetryService.track(
            event_name="cart.item_added",
            tenant_ctx=cmd.tenant_ctx,
            actor_ctx=actor_from_tenant_ctx(tenant_ctx=cmd.tenant_ctx, actor_type="CUSTOMER"),
            object_ref=ObjectRef(object_type="PRODUCT", object_id=product.id),
            properties={"quantity": quantity},
        )
        return GetCartUseCase.execute(cmd.tenant_ctx)

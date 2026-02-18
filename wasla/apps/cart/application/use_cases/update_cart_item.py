from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.cart.domain.errors import CartNotFoundError
from apps.cart.domain.policies import assert_cart_access, ensure_positive_quantity
from apps.cart.infrastructure.repositories import find_cart
from apps.tenants.domain.tenant_context import TenantContext

from .get_cart import GetCartUseCase


@dataclass(frozen=True)
class UpdateCartItemCommand:
    tenant_ctx: TenantContext
    item_id: int
    quantity: int


class UpdateCartItemUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: UpdateCartItemCommand):
        quantity = ensure_positive_quantity(cmd.quantity)
        cart = find_cart(cmd.tenant_ctx)
        if not cart:
            raise CartNotFoundError("Cart not found.")
        assert_cart_access(cart, cmd.tenant_ctx)

        item = cart.items.filter(id=cmd.item_id).first()
        if not item:
            raise CartNotFoundError("Cart item not found.")
        item.quantity = quantity
        item.save(update_fields=["quantity"])
        return GetCartUseCase.execute(cmd.tenant_ctx)

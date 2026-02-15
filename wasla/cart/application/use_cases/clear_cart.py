from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from cart.domain.errors import CartNotFoundError
from cart.domain.policies import assert_cart_access
from cart.infrastructure.repositories import find_cart
from tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class ClearCartCommand:
    tenant_ctx: TenantContext


class ClearCartUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: ClearCartCommand) -> None:
        cart = find_cart(cmd.tenant_ctx)
        if not cart:
            raise CartNotFoundError("Cart not found.")
        assert_cart_access(cart, cmd.tenant_ctx)
        cart.items.all().delete()

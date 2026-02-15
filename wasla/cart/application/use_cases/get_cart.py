from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from cart.domain.dtos import CartItemDTO, CartSummary
from cart.domain.policies import safe_decimal
from cart.infrastructure.repositories import find_cart, list_cart_items
from tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class GetCartCommand:
    tenant_ctx: TenantContext


class GetCartUseCase:
    @staticmethod
    def execute(tenant_ctx: TenantContext) -> CartSummary:
        cart = find_cart(tenant_ctx)
        if not cart:
            return CartSummary(cart_id=None, currency=tenant_ctx.currency or "SAR", items=[], subtotal=Decimal("0"), total=Decimal("0"))

        items = []
        subtotal = Decimal("0")
        for item in list_cart_items(cart):
            unit_price = safe_decimal(item.unit_price_snapshot)
            line_total = unit_price * item.quantity
            subtotal += line_total
            items.append(
                CartItemDTO(
                    id=item.id,
                    product_id=item.product_id,
                    name=getattr(item.product, "name", ""),
                    quantity=item.quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )
        total = subtotal
        return CartSummary(cart_id=cart.id, currency=cart.currency, items=items, subtotal=subtotal, total=total)

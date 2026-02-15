from __future__ import annotations

from typing import Iterable

from cart.models import Cart, CartItem
from tenants.domain.tenant_context import TenantContext


def get_or_create_cart(tenant_ctx: TenantContext) -> Cart:
    if tenant_ctx.user_id:
        cart, _ = Cart.objects.get_or_create(
            store_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            defaults={"currency": tenant_ctx.currency},
        )
        return cart
    if not tenant_ctx.session_key:
        raise ValueError("Session key is required for guest cart.")
    cart, _ = Cart.objects.get_or_create(
        store_id=tenant_ctx.tenant_id,
        session_key=tenant_ctx.session_key,
        defaults={"currency": tenant_ctx.currency},
    )
    return cart


def find_cart(tenant_ctx: TenantContext) -> Cart | None:
    if tenant_ctx.user_id:
        return Cart.objects.filter(store_id=tenant_ctx.tenant_id, user_id=tenant_ctx.user_id).first()
    if not tenant_ctx.session_key:
        return None
    return Cart.objects.filter(store_id=tenant_ctx.tenant_id, session_key=tenant_ctx.session_key).first()


def list_cart_items(cart: Cart) -> Iterable[CartItem]:
    return CartItem.objects.select_related("product").filter(cart=cart).order_by("id")

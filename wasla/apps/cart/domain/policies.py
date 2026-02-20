from __future__ import annotations

from decimal import Decimal

from apps.cart.domain.errors import CartAccessDeniedError, InvalidQuantityError
from apps.tenants.domain.tenant_context import TenantContext


def ensure_positive_quantity(quantity: int) -> int:
    if quantity < 1:
        raise InvalidQuantityError("Quantity must be at least 1.")
    return quantity


def assert_cart_access(cart, tenant_ctx: TenantContext) -> None:
    if cart.store_id != tenant_ctx.store_id:
        raise CartAccessDeniedError("Cart does not belong to tenant.")
    if tenant_ctx.user_id:
        if cart.user_id != tenant_ctx.user_id:
            raise CartAccessDeniedError("Cart does not belong to user.")
    else:
        if not tenant_ctx.session_key or cart.session_key != tenant_ctx.session_key:
            raise CartAccessDeniedError("Cart does not belong to session.")


def safe_decimal(value) -> Decimal:
    return Decimal(str(value or "0"))

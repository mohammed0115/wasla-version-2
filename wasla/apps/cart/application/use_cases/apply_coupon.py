from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.cart.domain.errors import CartError
from apps.cart.domain.policies import safe_decimal
from apps.cart.infrastructure.repositories import get_or_create_cart, list_cart_items
from apps.coupons.models import Coupon
from apps.coupons.services import CouponValidationService
from apps.tenants.domain.tenant_context import TenantContext

from .get_cart import GetCartUseCase


@dataclass(frozen=True)
class ApplyCouponCommand:
    tenant_ctx: TenantContext
    coupon_code: str


class ApplyCouponUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: ApplyCouponCommand):
        code = (cmd.coupon_code or "").strip()
        if not code:
            raise CartError("Coupon code is required.")

        cart = get_or_create_cart(cmd.tenant_ctx)
        items = list_cart_items(cart)
        if not items:
            raise CartError("Cart is empty.")

        subtotal = Decimal("0")
        for item in items:
            subtotal += safe_decimal(item.unit_price_snapshot) * item.quantity

        coupon = Coupon.objects.filter(
            store_id=cmd.tenant_ctx.store_id,
            code__iexact=code,
            is_active=True,
        ).first()
        if not coupon:
            raise CartError("Invalid coupon code.")

        is_valid, message = CouponValidationService().validate_coupon(
            coupon,
            customer=None,
            subtotal=subtotal,
        )
        if not is_valid:
            raise CartError(message or "Coupon not valid.")

        discount = safe_decimal(coupon.calculate_discount(subtotal))
        if discount <= 0:
            raise CartError("Coupon does not apply to this cart.")

        cart.applied_coupon_code = coupon.code
        cart.discount_amount = discount
        cart.save(update_fields=["applied_coupon_code", "discount_amount", "updated_at"])
        return GetCartUseCase.execute(cmd.tenant_ctx)


@dataclass(frozen=True)
class RemoveCouponCommand:
    tenant_ctx: TenantContext


class RemoveCouponUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: RemoveCouponCommand):
        cart = get_or_create_cart(cmd.tenant_ctx)
        cart.applied_coupon_code = ""
        cart.discount_amount = Decimal("0")
        cart.save(update_fields=["applied_coupon_code", "discount_amount", "updated_at"])
        return GetCartUseCase.execute(cmd.tenant_ctx)


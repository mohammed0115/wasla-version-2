from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apps.cart.domain.dtos import CartItemDTO, CartSummary
from apps.cart.domain.policies import safe_decimal
from apps.cart.infrastructure.repositories import find_cart, list_cart_items
from apps.tenants.domain.tenant_context import TenantContext
from apps.coupons.models import Coupon
from apps.coupons.services import CouponValidationService


@dataclass(frozen=True)
class GetCartCommand:
    tenant_ctx: TenantContext


class GetCartUseCase:
    @staticmethod
    def execute(tenant_ctx: TenantContext) -> CartSummary:
        cart = find_cart(tenant_ctx)
        if not cart:
            return CartSummary(
                cart_id=None,
                currency=tenant_ctx.currency or "SAR",
                items=[],
                subtotal=Decimal("0"),
                discount_amount=Decimal("0"),
                coupon_code=None,
                total=Decimal("0"),
            )

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
                    variant_id=item.variant_id,
                    variant_sku=getattr(item.variant, "sku", ""),
                    name=getattr(item.product, "name", ""),
                    quantity=item.quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )
        # Coupon revalidation to keep totals accurate when cart changes.
        coupon_code = (cart.applied_coupon_code or "").strip()
        discount_amount = Decimal("0")
        if coupon_code:
            coupon = Coupon.objects.filter(
                store_id=tenant_ctx.store_id,
                code__iexact=coupon_code,
                is_active=True,
            ).first()
            if coupon:
                is_valid, _ = CouponValidationService().validate_coupon(
                    coupon,
                    customer=None,
                    subtotal=subtotal,
                )
                if is_valid:
                    discount_amount = safe_decimal(coupon.calculate_discount(subtotal))
                else:
                    coupon_code = ""
            else:
                coupon_code = ""

        # Sync cart fields if needed
        if coupon_code != (cart.applied_coupon_code or "") or discount_amount != safe_decimal(cart.discount_amount):
            cart.applied_coupon_code = coupon_code
            cart.discount_amount = discount_amount
            cart.save(update_fields=["applied_coupon_code", "discount_amount", "updated_at"])

        total = max(Decimal("0"), subtotal - discount_amount)
        return CartSummary(
            cart_id=cart.id,
            currency=cart.currency,
            items=items,
            subtotal=subtotal,
            discount_amount=discount_amount,
            coupon_code=coupon_code or None,
            total=total,
        )

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.cart.application.use_cases.get_cart import GetCartUseCase
from apps.checkout.domain.errors import InvalidCheckoutStateError
from apps.checkout.models import CheckoutSession
from apps.customers.models import Customer
from apps.orders.models import Order
from apps.orders.services.order_service import OrderService
from apps.coupons.models import Coupon
from apps.coupons.services import CouponValidationService, CouponValidationError
from apps.catalog.models import Product
from apps.catalog.services.variant_service import ProductVariantService
from apps.tenants.domain.tenant_context import TenantContext
from apps.analytics.application.telemetry import TelemetryService, actor_from_tenant_ctx
from apps.analytics.domain.types import ObjectRef


@dataclass(frozen=True)
class CreateOrderFromCheckoutCommand:
    tenant_ctx: TenantContext
    session_id: int


class CreateOrderFromCheckoutUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: CreateOrderFromCheckoutCommand) -> Order:
        session = (
            CheckoutSession.objects.select_for_update()
            .filter(id=cmd.session_id, store_id=cmd.tenant_ctx.store_id)
            .first()
        )
        if not session:
            raise InvalidCheckoutStateError("Checkout session not found.")
        if session.order_id:
            return Order.objects.for_tenant(cmd.tenant_ctx.store_id).get(id=session.order_id)
        if session.status != CheckoutSession.STATUS_PAYMENT:
            raise InvalidCheckoutStateError("Checkout is not ready for payment.")

        cart_summary = GetCartUseCase.execute(cmd.tenant_ctx)
        if not cart_summary.items:
            raise InvalidCheckoutStateError("Cart is empty.")

        address = session.shipping_address_json or {}
        email = address.get("email", "").strip()
        full_name = address.get("full_name", "").strip()
        phone = address.get("phone", "").strip()
        if not email:
            raise InvalidCheckoutStateError("Email is required.")

        customer, _ = Customer.objects.get_or_create(
            store_id=cmd.tenant_ctx.store_id,
            email=email,
            defaults={"full_name": full_name or email, "is_active": True},
        )
        if full_name and customer.full_name != full_name:
            customer.full_name = full_name
            customer.save(update_fields=["full_name"])

        items = []
        for item in cart_summary.items:
            items.append(
                {
                    "product": None,
                    "variant": None,
                    "variant_id": item.variant_id,
                    "quantity": item.quantity,
                    "price": item.unit_price,
                    "product_id": item.product_id,
                }
            )

        product_map = {
            p.id: p
            for p in Product.objects.filter(
                store_id=cmd.tenant_ctx.store_id, id__in=[i["product_id"] for i in items]
            )
        }
        for item in items:
            product = product_map.get(item["product_id"])
            if not product:
                raise InvalidCheckoutStateError("Product not found for order.")
            item["product"] = product

        variant_map = ProductVariantService.get_variants_map(
            store_id=cmd.tenant_ctx.store_id,
            variant_ids=[item.get("variant_id") for item in items if item.get("variant_id")],
        )
        for item in items:
            variant_id = item.get("variant_id")
            if not variant_id:
                continue
            variant = variant_map.get(variant_id)
            if not variant or variant.product_id != item["product_id"]:
                raise InvalidCheckoutStateError("Variant not found for order.")
            item["variant"] = variant

        try:
            ProductVariantService.assert_checkout_stock(store_id=cmd.tenant_ctx.store_id, items=items)
        except ValueError as exc:
            raise InvalidCheckoutStateError(str(exc)) from exc

        order = OrderService.create_order(
            customer,
            items,
            store_id=cmd.tenant_ctx.store_id,
            tenant_id=cmd.tenant_ctx.tenant_id,
        )

        totals = session.totals_json or {}
        subtotal = Decimal(str(totals.get("subtotal") or cart_summary.subtotal))
        discount_amount = Decimal(str(totals.get("discount_amount") or cart_summary.discount_amount or "0"))
        shipping_fee = Decimal(str(totals.get("shipping_fee") or "0"))

        tax_rate = order.tax_rate or Decimal("0.15")
        taxable_base = subtotal - discount_amount + shipping_fee
        if taxable_base < 0:
            taxable_base = Decimal("0")
        tax_amount = (taxable_base * Decimal(str(tax_rate))).quantize(Decimal("0.01"))
        total_amount = (taxable_base + tax_amount).quantize(Decimal("0.01"))

        order.subtotal = subtotal
        order.discount_amount = discount_amount
        order.shipping_charge = shipping_fee
        order.tax_amount = tax_amount
        order.total_amount = total_amount
        order.currency = cmd.tenant_ctx.currency
        order.payment_status = "pending"
        order.customer_name = full_name
        order.customer_email = email
        order.customer_phone = phone
        order.shipping_address_json = address
        order.shipping_method_code = session.shipping_method_code
        order.save(
            update_fields=[
                "subtotal",
                "discount_amount",
                "shipping_charge",
                "tax_amount",
                "total_amount",
                "currency",
                "payment_status",
                "customer_name",
                "customer_email",
                "customer_phone",
                "shipping_address_json",
                "shipping_method_code",
            ]
        )

        # Apply coupon usage log (if applicable)
        coupon_code = cart_summary.coupon_code
        if coupon_code:
            coupon = Coupon.objects.filter(
                store_id=cmd.tenant_ctx.store_id,
                code__iexact=coupon_code,
                is_active=True,
            ).first()
            if coupon:
                is_valid, _ = CouponValidationService().validate_coupon(
                    coupon,
                    customer=customer,
                    subtotal=subtotal,
                )
                if is_valid and discount_amount > 0:
                    try:
                        CouponValidationService().apply_coupon(
                            coupon=coupon,
                            order=order,
                            discount_amount=discount_amount,
                        )
                        order.coupon_code = coupon.code
                        order.save(update_fields=["coupon_code"])
                    except CouponValidationError:
                        # Coupon usage not available anymore; remove discount to keep totals correct
                        order.discount_amount = Decimal("0")
                        taxable_base = order.subtotal + order.shipping_charge
                        if taxable_base < 0:
                            taxable_base = Decimal("0")
                        order.tax_amount = (taxable_base * Decimal(str(tax_rate))).quantize(Decimal("0.01"))
                        order.total_amount = (taxable_base + order.tax_amount).quantize(Decimal("0.01"))
                        order.coupon_code = ""
                        order.save(update_fields=["discount_amount", "tax_amount", "total_amount", "coupon_code"])
                    except Exception:
                        # Fail-safe: do not block order creation on coupon logging errors
                        pass

        session.order = order
        session.status = CheckoutSession.STATUS_CONFIRMED
        session.save(update_fields=["order", "status", "updated_at"])
        TelemetryService.track(
            event_name="order.placed",
            tenant_ctx=cmd.tenant_ctx,
            actor_ctx=actor_from_tenant_ctx(tenant_ctx=cmd.tenant_ctx, actor_type="CUSTOMER"),
            object_ref=ObjectRef(object_type="ORDER", object_id=order.id),
            properties={"total_amount": str(order.total_amount), "currency": order.currency},
        )
        return order

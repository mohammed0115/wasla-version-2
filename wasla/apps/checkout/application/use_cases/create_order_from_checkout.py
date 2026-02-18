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
from apps.catalog.models import Product
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
            .filter(id=cmd.session_id, store_id=cmd.tenant_ctx.tenant_id)
            .first()
        )
        if not session:
            raise InvalidCheckoutStateError("Checkout session not found.")
        if session.order_id:
            return Order.objects.get(id=session.order_id, store_id=cmd.tenant_ctx.tenant_id)
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
            store_id=cmd.tenant_ctx.tenant_id,
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
                    "quantity": item.quantity,
                    "price": item.unit_price,
                    "product_id": item.product_id,
                }
            )

        product_map = {
            p.id: p
            for p in Product.objects.filter(
                store_id=cmd.tenant_ctx.tenant_id, id__in=[i["product_id"] for i in items]
            )
        }
        for item in items:
            product = product_map.get(item["product_id"])
            if not product:
                raise InvalidCheckoutStateError("Product not found for order.")
            item["product"] = product

        order = OrderService.create_order(customer, items, store_id=cmd.tenant_ctx.tenant_id)

        totals = session.totals_json or {}
        total_amount = Decimal(str(totals.get("total") or order.total_amount))
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

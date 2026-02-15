from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from cart.application.use_cases.get_cart import GetCartUseCase
from checkout.domain.errors import EmptyCartError
from checkout.domain.policies import compute_totals
from checkout.models import CheckoutSession
from tenants.domain.tenant_context import TenantContext
from analytics.application.telemetry import TelemetryService, actor_from_tenant_ctx
from analytics.domain.types import ObjectRef


@dataclass(frozen=True)
class StartCheckoutCommand:
    tenant_ctx: TenantContext


class StartCheckoutUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: StartCheckoutCommand) -> CheckoutSession:
        cart_summary = GetCartUseCase.execute(cmd.tenant_ctx)
        if not cart_summary.items:
            raise EmptyCartError("Cart is empty.")

        session = (
            CheckoutSession.objects.select_for_update()
            .filter(cart_id=cart_summary.cart_id, store_id=cmd.tenant_ctx.tenant_id)
            .order_by("-id")
            .first()
        )
        if session and session.status != CheckoutSession.STATUS_CONFIRMED:
            return session

        totals = compute_totals(subtotal=cart_summary.subtotal, shipping_fee=Decimal("0"))
        created = CheckoutSession.objects.create(
            store_id=cmd.tenant_ctx.tenant_id,
            cart_id=cart_summary.cart_id,
            status=CheckoutSession.STATUS_ADDRESS,
            totals_json={k: str(v) for k, v in totals.items()},
        )
        TelemetryService.track(
            event_name="checkout.started",
            tenant_ctx=cmd.tenant_ctx,
            actor_ctx=actor_from_tenant_ctx(tenant_ctx=cmd.tenant_ctx, actor_type="CUSTOMER"),
            object_ref=ObjectRef(object_type="CART", object_id=cart_summary.cart_id),
            properties={"subtotal": str(cart_summary.subtotal)},
        )
        return created

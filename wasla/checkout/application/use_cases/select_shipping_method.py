from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from cart.application.use_cases.get_cart import GetCartUseCase
from checkout.domain.errors import InvalidCheckoutStateError
from checkout.domain.policies import compute_totals
from checkout.infrastructure.shipping_options import list_shipping_methods
from checkout.models import CheckoutSession
from tenants.domain.tenant_context import TenantContext
from analytics.application.telemetry import TelemetryService, actor_from_tenant_ctx
from analytics.domain.types import ObjectRef


@dataclass(frozen=True)
class SelectShippingMethodCommand:
    tenant_ctx: TenantContext
    session_id: int
    method_code: str


class SelectShippingMethodUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: SelectShippingMethodCommand) -> CheckoutSession:
        session = (
            CheckoutSession.objects.select_for_update()
            .filter(id=cmd.session_id, store_id=cmd.tenant_ctx.tenant_id)
            .first()
        )
        if not session:
            raise InvalidCheckoutStateError("Checkout session not found.")
        if session.status == CheckoutSession.STATUS_CONFIRMED:
            raise InvalidCheckoutStateError("Checkout already confirmed.")
        if not session.shipping_address_json:
            raise InvalidCheckoutStateError("Shipping address is required.")

        available = list_shipping_methods(tenant_id=cmd.tenant_ctx.tenant_id)
        chosen = next((m for m in available if m.code == cmd.method_code), None)
        if not chosen:
            raise InvalidCheckoutStateError("Shipping method not available.")

        cart_summary = GetCartUseCase.execute(cmd.tenant_ctx)
        totals = compute_totals(subtotal=cart_summary.subtotal, shipping_fee=Decimal(chosen.fee))
        session.shipping_method_code = chosen.code
        session.totals_json = {k: str(v) for k, v in totals.items()}
        session.status = CheckoutSession.STATUS_PAYMENT
        session.save(update_fields=["shipping_method_code", "totals_json", "status", "updated_at"])
        TelemetryService.track(
            event_name="checkout.shipping_selected",
            tenant_ctx=cmd.tenant_ctx,
            actor_ctx=actor_from_tenant_ctx(tenant_ctx=cmd.tenant_ctx, actor_type="CUSTOMER"),
            object_ref=ObjectRef(object_type="CHECKOUT", object_id=session.id),
            properties={"method_code": chosen.code, "shipping_fee": str(chosen.fee)},
        )
        return session

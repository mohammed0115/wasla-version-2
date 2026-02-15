from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from checkout.domain.errors import InvalidCheckoutStateError
from checkout.domain.policies import validate_address
from checkout.models import CheckoutSession
from tenants.domain.tenant_context import TenantContext
from analytics.application.telemetry import TelemetryService, actor_from_tenant_ctx
from analytics.domain.types import ObjectRef


@dataclass(frozen=True)
class SaveShippingAddressCommand:
    tenant_ctx: TenantContext
    session_id: int
    address: dict


class SaveShippingAddressUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: SaveShippingAddressCommand) -> CheckoutSession:
        session = (
            CheckoutSession.objects.select_for_update()
            .filter(id=cmd.session_id, store_id=cmd.tenant_ctx.tenant_id)
            .first()
        )
        if not session:
            raise InvalidCheckoutStateError("Checkout session not found.")
        if session.status == CheckoutSession.STATUS_CONFIRMED:
            raise InvalidCheckoutStateError("Checkout already confirmed.")

        session.shipping_address_json = validate_address(cmd.address)
        session.status = CheckoutSession.STATUS_SHIPPING
        session.save(update_fields=["shipping_address_json", "status", "updated_at"])
        TelemetryService.track(
            event_name="checkout.address_saved",
            tenant_ctx=cmd.tenant_ctx,
            actor_ctx=actor_from_tenant_ctx(tenant_ctx=cmd.tenant_ctx, actor_type="CUSTOMER"),
            object_ref=ObjectRef(object_type="CHECKOUT", object_id=session.id),
            properties={
                "has_email": bool((cmd.address or {}).get("email")),
                "has_phone": bool((cmd.address or {}).get("phone")),
            },
        )
        return session

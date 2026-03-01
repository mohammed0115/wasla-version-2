from __future__ import annotations

from dataclasses import dataclass

from apps.checkout.domain.dtos import CheckoutSummary
from apps.checkout.domain.errors import InvalidCheckoutStateError
from apps.checkout.infrastructure.shipping_options import list_shipping_methods
from apps.cart.application.use_cases.get_cart import GetCartUseCase
from apps.checkout.models import CheckoutSession
from apps.tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class GetCheckoutCommand:
    tenant_ctx: TenantContext
    session_id: int


class GetCheckoutUseCase:
    @staticmethod
    def execute(cmd: GetCheckoutCommand) -> CheckoutSummary:
        session = CheckoutSession.objects.filter(
            id=cmd.session_id, store_id=cmd.tenant_ctx.store_id
        ).first()
        if not session:
            raise InvalidCheckoutStateError("Checkout session not found.")

        cart_summary = GetCartUseCase.execute(cmd.tenant_ctx)
        methods = list_shipping_methods(
            tenant_id=cmd.tenant_ctx.store_id,
            address=session.shipping_address_json or {},
            cart_summary=cart_summary,
        )
        totals = session.totals_json or {}
        return CheckoutSummary(session_id=session.id, status=session.status, totals=totals, shipping_methods=methods)

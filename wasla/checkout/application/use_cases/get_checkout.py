from __future__ import annotations

from dataclasses import dataclass

from checkout.domain.dtos import CheckoutSummary
from checkout.domain.errors import InvalidCheckoutStateError
from checkout.infrastructure.shipping_options import list_shipping_methods
from checkout.models import CheckoutSession
from tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class GetCheckoutCommand:
    tenant_ctx: TenantContext
    session_id: int


class GetCheckoutUseCase:
    @staticmethod
    def execute(cmd: GetCheckoutCommand) -> CheckoutSummary:
        session = CheckoutSession.objects.filter(
            id=cmd.session_id, store_id=cmd.tenant_ctx.tenant_id
        ).first()
        if not session:
            raise InvalidCheckoutStateError("Checkout session not found.")

        methods = list_shipping_methods(tenant_id=cmd.tenant_ctx.tenant_id)
        totals = session.totals_json or {}
        return CheckoutSummary(session_id=session.id, status=session.status, totals=totals, shipping_methods=methods)

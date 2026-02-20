from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.orders.models import Order
from apps.payments.application.facade import PaymentGatewayFacade
from apps.payments.domain.ports import PaymentRedirect
from apps.payments.models import PaymentIntent
from apps.payments.application.use_cases.payment_outcomes import apply_payment_success
from apps.tenants.domain.tenant_context import TenantContext
from apps.analytics.application.telemetry import TelemetryService, actor_from_tenant_ctx
from apps.analytics.domain.types import ObjectRef


@dataclass(frozen=True)
class InitiatePaymentCommand:
    tenant_ctx: TenantContext
    order_id: int
    provider_code: str
    return_url: str


class InitiatePaymentUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: InitiatePaymentCommand) -> PaymentRedirect:
        order = (
            Order.objects.for_tenant(cmd.tenant_ctx.store_id)
            .select_for_update()
            .filter(id=cmd.order_id)
            .first()
        )
        if not order:
            raise ValueError("Order not found.")
        if order.payment_status == "paid":
            return PaymentRedirect(redirect_url=cmd.return_url, client_secret=None, provider_reference=None)

        gateway = PaymentGatewayFacade.get(cmd.provider_code, tenant_id=cmd.tenant_ctx.tenant_id)
        idempotency_key = f"{gateway.code}:{order.id}"
        intent, _ = PaymentIntent.objects.get_or_create(
            tenant_id=cmd.tenant_ctx.tenant_id,
            store_id=cmd.tenant_ctx.store_id,
            order=order,
            provider_code=gateway.code,
            idempotency_key=idempotency_key,
            defaults={
                "amount": order.total_amount,
                "currency": order.currency or cmd.tenant_ctx.currency,
                "status": "pending",
            },
        )

        redirect = gateway.initiate_payment(
            order=order,
            amount=order.total_amount,
            currency=order.currency or cmd.tenant_ctx.currency,
            return_url=cmd.return_url,
        )
        if not intent.provider_reference:
            intent.provider_reference = redirect.provider_reference or ""
            intent.save(update_fields=["provider_reference"])

        TelemetryService.track(
            event_name="payment.initiated",
            tenant_ctx=cmd.tenant_ctx,
            actor_ctx=actor_from_tenant_ctx(tenant_ctx=cmd.tenant_ctx, actor_type="CUSTOMER"),
            object_ref=ObjectRef(object_type="ORDER", object_id=order.id),
            properties={"provider_code": gateway.code, "amount": str(order.total_amount)},
        )

        if gateway.code == "dummy":
            apply_payment_success(intent=intent, order=order, tenant_ctx=cmd.tenant_ctx)
            return PaymentRedirect(
                redirect_url=cmd.return_url,
                client_secret=None,
                provider_reference=intent.provider_reference,
            )

        return redirect

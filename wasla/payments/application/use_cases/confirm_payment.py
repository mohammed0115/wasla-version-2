from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from orders.models import Order
from payments.application.facade import PaymentGatewayFacade
from payments.application.use_cases.payment_outcomes import (
    apply_payment_failure,
    apply_payment_success,
)
from payments.models import PaymentEvent, PaymentIntent
from tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class ConfirmPaymentCommand:
    tenant_ctx: TenantContext
    provider_code: str
    payload: dict
    headers: dict
    raw_body: str = ""


class ConfirmPaymentUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: ConfirmPaymentCommand) -> PaymentIntent:
        gateway = PaymentGatewayFacade.get(cmd.provider_code, tenant_id=cmd.tenant_ctx.tenant_id)
        verified = gateway.verify_callback(
            payload=cmd.payload,
            headers=cmd.headers,
            raw_body=cmd.raw_body or "",
        )

        PaymentEvent.objects.create(
            provider_code=gateway.code,
            event_id=verified.event_id,
            payload_json=cmd.payload,
            payload_raw=cmd.raw_body or "",
        )

        intent = PaymentIntent.objects.select_for_update().filter(
            store_id=cmd.tenant_ctx.tenant_id,
            provider_code=gateway.code,
            provider_reference=verified.intent_reference,
        ).first()
        if not intent:
            raise ValueError("Payment intent not found.")

        order = Order.objects.select_for_update().filter(
            id=intent.order_id,
            store_id=cmd.tenant_ctx.tenant_id,
        ).first()
        if not order:
            raise ValueError("Order not found.")

        if verified.status == "succeeded":
            apply_payment_success(intent=intent, order=order, tenant_ctx=cmd.tenant_ctx)
        elif verified.status == "failed":
            apply_payment_failure(intent=intent, order=order, tenant_ctx=cmd.tenant_ctx)
        elif verified.status in {"pending", "requires_action"}:
            next_status = "requires_action" if verified.status == "requires_action" else "pending"
            if intent.status != next_status:
                intent.status = next_status
                intent.save(update_fields=["status"])

        return intent

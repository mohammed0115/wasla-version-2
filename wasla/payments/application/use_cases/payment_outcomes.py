from __future__ import annotations

from analytics.application.telemetry import TelemetryService, actor_from_tenant_ctx
from analytics.domain.types import ObjectRef
from orders.models import Order
from orders.services.order_service import OrderService
from orders.application.use_cases.notify_merchant_order_placed import (
    NotifyMerchantOrderPlacedCommand,
    NotifyMerchantOrderPlacedUseCase,
)
from payments.models import Payment, PaymentIntent
from settlements.application.use_cases.credit_order_payment import (
    CreditOrderPaymentCommand,
    CreditOrderPaymentUseCase,
)
from tenants.domain.tenant_context import TenantContext


def apply_payment_success(*, intent: PaymentIntent, order: Order, tenant_ctx: TenantContext) -> None:
    if intent.status != "succeeded":
        intent.status = "succeeded"
        intent.save(update_fields=["status"])

    was_paid = order.payment_status == "paid" or order.status == "paid"
    if not was_paid:
        OrderService.mark_as_paid(order)
        if getattr(order, "payment_status", None) != "paid":
            order.payment_status = "paid"
            order.save(update_fields=["payment_status"])

    reference = intent.provider_reference or intent.idempotency_key
    exists = Payment.objects.filter(
        order=order,
        method=intent.provider_code,
        reference=reference,
    ).exists()
    if not exists:
        Payment.objects.create(
            order=order,
            method=intent.provider_code,
            status="success",
            amount=intent.amount,
            reference=reference,
        )

    CreditOrderPaymentUseCase.execute(CreditOrderPaymentCommand(order_id=order.id))

    if not was_paid:
        NotifyMerchantOrderPlacedUseCase.execute(
            NotifyMerchantOrderPlacedCommand(order_id=order.id, tenant_id=tenant_ctx.tenant_id)
        )
        TelemetryService.track(
            event_name="payment.succeeded",
            tenant_ctx=tenant_ctx,
            actor_ctx=actor_from_tenant_ctx(tenant_ctx=tenant_ctx, actor_type="CUSTOMER"),
            object_ref=ObjectRef(object_type="ORDER", object_id=order.id),
            properties={"provider_code": intent.provider_code, "amount": str(intent.amount)},
        )


def apply_payment_failure(*, intent: PaymentIntent, order: Order, tenant_ctx: TenantContext) -> None:
    if order.payment_status == "paid" or order.status == "paid":
        return
    if intent.status != "failed":
        intent.status = "failed"
        intent.save(update_fields=["status"])
    if order.payment_status != "failed":
        order.payment_status = "failed"
        order.save(update_fields=["payment_status"])
    TelemetryService.track(
        event_name="payment.failed",
        tenant_ctx=tenant_ctx,
        actor_ctx=actor_from_tenant_ctx(tenant_ctx=tenant_ctx, actor_type="CUSTOMER"),
        object_ref=ObjectRef(object_type="ORDER", object_id=order.id),
        properties={"provider_code": intent.provider_code, "reason_code": "provider_failed"},
    )

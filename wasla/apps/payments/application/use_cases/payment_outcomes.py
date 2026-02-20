from __future__ import annotations

from apps.analytics.application.telemetry import TelemetryService, actor_from_tenant_ctx
from apps.analytics.domain.types import ObjectRef
from apps.orders.models import Order
from apps.orders.services.order_service import OrderService
from apps.orders.application.use_cases.notify_merchant_order_placed import (
    NotifyMerchantOrderPlacedCommand,
    NotifyMerchantOrderPlacedUseCase,
)
from apps.payments.models import Payment, PaymentIntent
from apps.settlements.application.use_cases.credit_order_payment import (
    CreditOrderPaymentCommand,
    CreditOrderPaymentUseCase,
)
from apps.shipping.services.shipping_service import ShippingService
from apps.sms.application.use_cases.send_sms import SendSmsCommand, SendSmsUseCase
from apps.tenants.models import Tenant
from apps.tenants.domain.tenant_context import TenantContext


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
            tenant_id=order.tenant_id or order.store_id,
            order=order,
            method=intent.provider_code,
            status="success",
            amount=intent.amount,
            reference=reference,
        )

    CreditOrderPaymentUseCase.execute(CreditOrderPaymentCommand(order_id=order.id))

    shipment = None
    if not order.shipments.exists() and order.status in {"paid", "processing"}:
        if order.status == "paid":
            order.status = "processing"
            order.save(update_fields=["status"])
        carrier = (getattr(order, "shipping_method_code", "") or "manual_delivery").strip()
        try:
            shipment = ShippingService.create_shipment(order=order, carrier=carrier)
        except ValueError:
            pass

    if not was_paid and getattr(order, "customer_phone", ""):
        tenant = Tenant.objects.filter(id=tenant_ctx.tenant_id).first()
        sms_body = (
            f"Your order {order.order_number} is confirmed. "
            f"Amount: {order.total_amount} {order.currency}."
        )
        try:
            SendSmsUseCase.execute(
                SendSmsCommand(
                    body=sms_body,
                    recipients=[order.customer_phone],
                    tenant=tenant,
                    metadata={"order_id": order.id, "event": "order_confirmed"},
                )
            )
        except Exception:
            pass

        if shipment and shipment.tracking_number:
            shipment_sms_body = (
                f"Your order {order.order_number} has been shipped. "
                f"Tracking: {shipment.tracking_number}."
            )
            try:
                SendSmsUseCase.execute(
                    SendSmsCommand(
                        body=shipment_sms_body,
                        recipients=[order.customer_phone],
                        tenant=tenant,
                        metadata={"order_id": order.id, "event": "order_shipped"},
                    )
                )
            except Exception:
                pass

    if not was_paid:
        NotifyMerchantOrderPlacedUseCase.execute(
            NotifyMerchantOrderPlacedCommand(order_id=order.id, tenant_id=tenant_ctx.store_id)
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

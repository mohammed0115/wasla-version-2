from __future__ import annotations

import hashlib
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from orders.models import Order
from payments.application.facade import PaymentGatewayFacade
from payments.application.use_cases.payment_outcomes import (
    apply_payment_failure,
    apply_payment_success,
)
from payments.models import PaymentIntent, PaymentEvent
from webhooks.models import WebhookEvent
from tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class HandleWebhookEventCommand:
    provider_code: str
    headers: dict
    payload: dict
    raw_body: str = ""


class HandleWebhookEventUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: HandleWebhookEventCommand) -> WebhookEvent:
        raw_body = cmd.raw_body or ""
        try:
            _, verified, tenant_id = PaymentGatewayFacade.resolve_for_webhook(
                cmd.provider_code,
                headers=cmd.headers,
                payload=cmd.payload,
                raw_body=raw_body,
            )
        except ValueError as exc:
            event = HandleWebhookEventUseCase._record_invalid_event(cmd, raw_body=raw_body)
            if not event.processing_status:
                event.processing_status = WebhookEvent.STATUS_FAILED
                event.processed_at = timezone.now()
                event.save(update_fields=["processing_status", "processed_at"])
            raise

        idempotency_key = f"{cmd.provider_code}:{tenant_id}:{verified.event_id}"
        event = WebhookEvent.objects.select_for_update().filter(idempotency_key=idempotency_key).first()
        if event and event.processing_status == WebhookEvent.STATUS_PROCESSED:
            return event

        if not event:
            event = WebhookEvent.objects.create(
                provider_code=cmd.provider_code,
                event_id=verified.event_id,
                idempotency_key=idempotency_key,
                payload_json=cmd.payload,
                payload_raw=raw_body,
                processing_status=WebhookEvent.STATUS_PENDING,
            )
        elif not event.payload_raw and raw_body:
            event.payload_raw = raw_body
            event.save(update_fields=["payload_raw"])

        PaymentEvent.objects.create(
            provider_code=cmd.provider_code,
            event_id=verified.event_id,
            payload_json=cmd.payload,
            payload_raw=raw_body,
        )

        intent = PaymentIntent.objects.select_for_update().filter(
            provider_code=cmd.provider_code,
            provider_reference=verified.intent_reference,
            store_id=tenant_id,
        ).first()
        if not intent:
            event.processing_status = WebhookEvent.STATUS_FAILED
            event.processed_at = timezone.now()
            event.save(update_fields=["processing_status", "processed_at"])
            return event

        order = Order.objects.select_for_update().filter(id=intent.order_id, store_id=intent.store_id).first()
        if not order:
            event.processing_status = WebhookEvent.STATUS_FAILED
            event.processed_at = timezone.now()
            event.save(update_fields=["processing_status", "processed_at"])
            return event

        tenant_ctx = TenantContext(
            tenant_id=order.store_id,
            currency=order.currency,
            user_id=None,
            session_key="",
        )
        if verified.status == "succeeded":
            apply_payment_success(intent=intent, order=order, tenant_ctx=tenant_ctx)
        elif verified.status == "failed":
            apply_payment_failure(intent=intent, order=order, tenant_ctx=tenant_ctx)
        elif verified.status in {"pending", "requires_action"}:
            next_status = "requires_action" if verified.status == "requires_action" else "pending"
            if intent.status != next_status:
                intent.status = next_status
                intent.save(update_fields=["status"])

        event.processing_status = WebhookEvent.STATUS_PROCESSED
        event.processed_at = timezone.now()
        event.save(update_fields=["processing_status", "processed_at"])
        return event

    @staticmethod
    def _record_invalid_event(cmd: HandleWebhookEventCommand, *, raw_body: str) -> WebhookEvent:
        payload_hash = hashlib.sha256(raw_body.encode("utf-8")).hexdigest() if raw_body else "empty"
        event_id = cmd.payload.get("event_id") or "invalid"
        idempotency_key = f"{cmd.provider_code}:invalid:{payload_hash}"
        event, _ = WebhookEvent.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "provider_code": cmd.provider_code,
                "event_id": str(event_id),
                "payload_json": cmd.payload,
                "payload_raw": raw_body,
                "processing_status": WebhookEvent.STATUS_FAILED,
                "processed_at": timezone.now(),
            },
        )
        return event

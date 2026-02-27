from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
import hashlib

from django.db import transaction
from django.utils import timezone

from apps.orders.models import Order
from apps.payments.application.facade import PaymentGatewayFacade
from apps.payments.application.use_cases.payment_outcomes import (
    apply_payment_failure,
    apply_payment_success,
)
from apps.payments.models import PaymentIntent, PaymentEvent, PaymentProviderSettings, WebhookEvent, PaymentAttempt
from apps.payments.security import WebhookSecurityValidator, ProviderCommunicationLogger
from apps.payments.state_machine import transition_payment_attempt_status
from apps.tenants.domain.tenant_context import TenantContext
from apps.payments.structured_logging import log_payment_structured


@dataclass(frozen=True)
class HandleWebhookEventCommand:
    provider_code: str
    headers: dict
    payload: dict
    raw_body: str = ""


class HandleWebhookEventUseCase:
    @staticmethod
    def execute(cmd: HandleWebhookEventCommand) -> WebhookEvent:
        raw_body = cmd.raw_body or ""

        signature_header = cmd.headers.get("X-Webhook-Signature") or cmd.headers.get("X-Signature") or ""
        timestamp = WebhookSecurityValidator.extract_timestamp_from_header(
            cmd.headers.get("X-Webhook-Timestamp") or cmd.headers.get("X-Timestamp") or ""
        )

        try:
            _, verified, tenant_id = PaymentGatewayFacade.resolve_for_webhook(
                cmd.provider_code,
                headers=cmd.headers,
                payload=cmd.payload,
                raw_body=raw_body,
            )
        except ValueError:
            raise

        provider_settings = PaymentProviderSettings.objects.filter(
            tenant_id=tenant_id,
            provider_code=cmd.provider_code,
            is_enabled=True,
        ).first()

        intent = (
            PaymentIntent.objects
            .filter(
                tenant_id=tenant_id,
                provider_code=cmd.provider_code,
                provider_reference=verified.intent_reference,
            )
            .first()
        )
        store_id = intent.store_id if intent else None

        with transaction.atomic():
            event_defaults = {
                "provider": cmd.provider_code,
                "provider_name": cmd.provider_code,
                "payload": cmd.payload,
                "raw_payload": raw_body,
                "status": WebhookEvent.STATUS_RECEIVED,
                "signature": signature_header,
                "webhook_timestamp": datetime.fromtimestamp(timestamp, tz=dt_timezone.utc) if timestamp else None,
            }
            event, _ = WebhookEvent.objects.select_for_update().get_or_create(
                store_id=store_id,
                event_id=verified.event_id,
                defaults=event_defaults,
            )

            if event.processed or event.status == WebhookEvent.STATUS_PROCESSED:
                return event

            if event.status == WebhookEvent.STATUS_PROCESSING:
                return event

            secret = getattr(provider_settings, "webhook_secret", "")
            tolerance_seconds = getattr(provider_settings, "webhook_tolerance_seconds", 300) or 300

            signature_ok = bool(secret) and WebhookSecurityValidator.verify_signature(
                payload=raw_body,
                signature=signature_header,
                secret=secret,
                algorithm="sha256",
            )
            if not signature_ok:
                event.signature_verified = False
                event.signature_valid = False
                event.status = WebhookEvent.STATUS_FAILED
                event.last_error = "invalid_signature"
                event.processed = False
                event.save(
                    update_fields=[
                        "signature_verified",
                        "signature_valid",
                        "status",
                        "last_error",
                        "processed",
                    ]
                )
                raise ValueError("invalid_signature")

            if not timestamp or not WebhookSecurityValidator.check_replay_attack(
                webhook_timestamp=timestamp,
                tolerance_seconds=tolerance_seconds,
            ):
                event.signature_verified = True
                event.signature_valid = True
                event.status = WebhookEvent.STATUS_FAILED
                event.last_error = "replay_detected"
                event.processed = False
                event.save(
                    update_fields=[
                        "signature_verified",
                        "signature_valid",
                        "status",
                        "last_error",
                        "processed",
                    ]
                )
                raise ValueError("replay_detected")

            event.signature_verified = True
            event.signature_valid = True
            event.status = WebhookEvent.STATUS_PROCESSING
            event.processed = False
            event.idempotency_checked = True
            event.payload_hash = hashlib.sha256(raw_body.encode("utf-8")).hexdigest() if raw_body else ""
            event.save(
                update_fields=[
                    "signature_verified",
                    "signature_valid",
                    "status",
                    "processed",
                    "idempotency_checked",
                    "payload_hash",
                ]
            )

            # Log webhook receipt with structured logging
            ProviderCommunicationLogger.log_communication(
                tenant_id=tenant_id,
                provider_code=cmd.provider_code,
                operation="webhook_received",
                request_data={"event_id": verified.event_id, "event_type": verified.status},
                response_data={"signature_verified": True, "security_error": ""},
                idempotency_key=f"{cmd.provider_code}:{tenant_id}:{verified.event_id}",
                status_code=200,
                attempt_number=1,
            )

            log_payment_structured(
                event="webhook_received",
                store_id=store_id,
                order_id=intent.order_id if intent else None,
                provider=cmd.provider_code,
                idempotency_key=f"{cmd.provider_code}:{tenant_id}:{verified.event_id}",
                status="received",
            )

            PaymentEvent.objects.create(
                provider_code=cmd.provider_code,
                event_id=verified.event_id,
                payload_json=cmd.payload,
                payload_raw=raw_body,
            )

            if not intent:
                event.status = WebhookEvent.STATUS_FAILED
                event.processed_at = timezone.now()
                event.processed = False
                event.last_error = "intent_not_found"
                event.save(update_fields=["status", "processed_at", "processed", "last_error"])
                return event

            intent_store_id = intent.store_id
            order = (
                Order.objects.for_tenant(intent_store_id)
                .select_for_update()
                .filter(id=intent.order_id)
                .first()
            )
            if not order:
                event.status = WebhookEvent.STATUS_FAILED
                event.processed_at = timezone.now()
                event.processed = False
                event.last_error = "order_not_found"
                event.save(update_fields=["status", "processed_at", "processed", "last_error"])
                return event

            attempt = (
                PaymentAttempt.objects.select_for_update()
                .filter(
                    order=order,
                    provider=cmd.provider_code,
                )
                .order_by("-created_at")
                .first()
            )

            if intent.is_flagged or (attempt and attempt.is_flagged):
                if attempt:
                    transition_payment_attempt_status(attempt, PaymentAttempt.STATUS_FLAGGED, reason="risk_review_required")
                    attempt.webhook_received = True
                    attempt.webhook_verified = True
                    attempt.webhook_event = event
                    attempt.save(update_fields=["webhook_received", "webhook_verified", "webhook_event", "updated_at"])
                event.status = WebhookEvent.STATUS_IGNORED
                event.processed = True
                event.processed_at = timezone.now()
                event.save(update_fields=["status", "processed", "processed_at"])
                return event

            tenant_ctx = TenantContext(
                tenant_id=tenant_id,
                store_id=order.store_id,
                currency=order.currency,
                user_id=None,
                session_key="",
            )
            if verified.status == "succeeded":
                apply_payment_success(intent=intent, order=order, tenant_ctx=tenant_ctx)
                if attempt:
                    transition_payment_attempt_status(attempt, PaymentAttempt.STATUS_CONFIRMED, reason="webhook_succeeded")
            elif verified.status == "failed":
                apply_payment_failure(intent=intent, order=order, tenant_ctx=tenant_ctx)
                if attempt:
                    transition_payment_attempt_status(attempt, PaymentAttempt.STATUS_FAILED, reason="webhook_failed")
            elif verified.status in {"pending", "requires_action"}:
                next_status = "requires_action" if verified.status == "requires_action" else "pending"
                if intent.status != next_status:
                    intent.status = next_status
                    intent.save(update_fields=["status"])
                if attempt:
                    transition_payment_attempt_status(attempt, PaymentAttempt.STATUS_PENDING, reason="webhook_pending")

            if attempt:
                attempt.webhook_received = True
                attempt.webhook_verified = True
                attempt.webhook_event = event
                attempt.save(update_fields=["webhook_received", "webhook_verified", "webhook_event", "updated_at"])

            event.status = WebhookEvent.STATUS_PROCESSED
            event.processed = True
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "processed", "processed_at"])
            return event

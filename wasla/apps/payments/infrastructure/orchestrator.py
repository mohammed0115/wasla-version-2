from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.utils import IntegrityError
from django.utils import timezone

from apps.payments.infrastructure.providers.base import BasePaymentProvider
from apps.payments.infrastructure.providers.paypal import PayPalPaymentProvider
from apps.payments.infrastructure.providers.stripe import StripePaymentProvider
from apps.payments.infrastructure.providers.tap import TapPaymentProvider
from apps.payments.models import PaymentAttempt, PaymentProviderSettings, WebhookEvent
from apps.settlements.application.use_cases.process_successful_payment import (
    process_successful_payment,
)


class PaymentOrchestrator:
    """Unified payment orchestration layer with provider strategy selection."""

    PROVIDERS: dict[str, type[BasePaymentProvider]] = {
        "tap": TapPaymentProvider,
        "stripe": StripePaymentProvider,
        "paypal": PayPalPaymentProvider,
    }

    @classmethod
    def _get_provider_settings(cls, payment_attempt: PaymentAttempt) -> PaymentProviderSettings:
        settings = (
            PaymentProviderSettings.objects.select_related("store", "tenant")
            .filter(
                store=payment_attempt.store,
                provider=payment_attempt.provider,
                is_active=True,
            )
            .first()
        )
        if settings:
            return settings
        raise ValueError(
            f"Active payment provider settings not found for store={payment_attempt.store_id} provider={payment_attempt.provider}"
        )

    @classmethod
    def _get_provider(cls, payment_attempt: PaymentAttempt) -> BasePaymentProvider:
        provider_cls = cls.PROVIDERS.get(payment_attempt.provider)
        if not provider_cls:
            raise ValueError(f"Unsupported payment provider: {payment_attempt.provider}")
        settings = cls._get_provider_settings(payment_attempt)
        return provider_cls(settings)

    @staticmethod
    def _standard_response(*, ok: bool, payment_attempt: PaymentAttempt, **extra: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": ok,
            "payment_attempt_id": payment_attempt.id,
            "status": payment_attempt.status,
            "provider": payment_attempt.provider,
            "provider_reference": payment_attempt.provider_reference,
        }
        payload.update(extra)
        return payload

    @classmethod
    @transaction.atomic
    def create_payment(cls, payment_attempt: PaymentAttempt) -> dict[str, Any]:
        locked_attempt = PaymentAttempt.objects.select_for_update().get(pk=payment_attempt.pk)

        existing = (
            PaymentAttempt.objects.select_for_update()
            .filter(idempotency_key=locked_attempt.idempotency_key)
            .exclude(pk=locked_attempt.pk)
            .first()
        )
        if existing:
            return cls._standard_response(
                ok=True,
                payment_attempt=existing,
                redirect_url=existing.raw_response.get("redirect_url", ""),
                idempotent_reuse=True,
                raw=existing.raw_response,
            )

        provider = cls._get_provider(locked_attempt)
        result = provider.create_payment(locked_attempt)

        locked_attempt.provider_reference = result.get("provider_reference", "")
        locked_attempt.raw_response = result.get("raw", {})
        locked_attempt.status = PaymentAttempt.STATUS_PENDING
        locked_attempt.save(update_fields=["provider_reference", "raw_response", "status", "updated_at"])

        return cls._standard_response(
            ok=True,
            payment_attempt=locked_attempt,
            redirect_url=result.get("redirect_url", ""),
            raw=result.get("raw", {}),
        )

    @classmethod
    @transaction.atomic
    def verify_payment(cls, payment_attempt: PaymentAttempt, data: dict[str, Any]) -> dict[str, Any]:
        locked_attempt = PaymentAttempt.objects.select_for_update().get(pk=payment_attempt.pk)
        provider = cls._get_provider(locked_attempt)
        result = provider.verify_payment(data)

        locked_attempt.provider_reference = result.get("provider_reference") or locked_attempt.provider_reference
        locked_attempt.raw_response = result.get("raw", {})
        locked_attempt.status = (
            PaymentAttempt.STATUS_PAID if bool(result.get("paid")) else PaymentAttempt.STATUS_FAILED
        )
        locked_attempt.save(update_fields=["provider_reference", "raw_response", "status", "updated_at"])

        return cls._standard_response(
            ok=bool(result.get("paid")),
            payment_attempt=locked_attempt,
            paid=bool(result.get("paid")),
            raw=result.get("raw", {}),
        )

    @classmethod
    @transaction.atomic
    def refund(cls, payment_attempt: PaymentAttempt, amount: Decimal) -> dict[str, Any]:
        locked_attempt = PaymentAttempt.objects.select_for_update().get(pk=payment_attempt.pk)
        provider = cls._get_provider(locked_attempt)
        result = provider.refund(locked_attempt, amount)

        if bool(result.get("ok")):
            locked_attempt.status = PaymentAttempt.STATUS_REFUNDED
            locked_attempt.raw_response = result.get("raw", {})
            locked_attempt.provider_reference = result.get("provider_reference") or locked_attempt.provider_reference
            locked_attempt.save(update_fields=["status", "raw_response", "provider_reference", "updated_at"])

        return cls._standard_response(
            ok=bool(result.get("ok")),
            payment_attempt=locked_attempt,
            refunded_amount=str(amount),
            raw=result.get("raw", {}),
        )

    @classmethod
    def validate_webhook(cls, provider: str, request) -> bool:
        provider_cls = cls.PROVIDERS.get(provider)
        if not provider_cls:
            return False

        settings = (
            PaymentProviderSettings.objects.filter(provider=provider, is_active=True)
            .order_by("id")
            .first()
        )
        if not settings:
            return False

        return provider_cls(settings).validate_webhook(request)

    @classmethod
    def parse_webhook(cls, provider: str, request) -> dict[str, Any]:
        provider_cls = cls.PROVIDERS.get(provider)
        if not provider_cls:
            return {}

        settings = (
            PaymentProviderSettings.objects.filter(provider=provider, is_active=True)
            .order_by("id")
            .first()
        )
        if not settings:
            return {}

        return provider_cls(settings).parse_webhook(request)

    @classmethod
    def _get_provider_for_webhook(cls, provider: str) -> BasePaymentProvider:
        provider_cls = cls.PROVIDERS.get(provider)
        if not provider_cls:
            raise ValueError(f"Unsupported payment provider: {provider}")
        settings = (
            PaymentProviderSettings.objects.filter(provider=provider, is_active=True)
            .order_by("id")
            .first()
        )
        if not settings:
            raise ValueError(f"Active payment provider settings not found for provider={provider}")
        return provider_cls(settings)

    @classmethod
    @transaction.atomic
    def process_webhook(cls, provider: str, request) -> dict[str, Any]:
        provider_key = (provider or "").strip().lower()
        provider_impl = cls._get_provider_for_webhook(provider_key)
        normalized = provider_impl.parse_webhook(request)

        event_id = str(normalized.get("event_id") or "").strip()
        if not event_id:
            raise ValueError("missing_event_id")

        payload = normalized.get("raw") if isinstance(normalized.get("raw"), dict) else {}

        try:
            event, created = WebhookEvent.objects.get_or_create(
                provider=provider_key,
                event_id=event_id,
                defaults={
                    "payload": payload,
                    "status": WebhookEvent.STATUS_RECEIVED,
                },
            )
        except IntegrityError:
            event = WebhookEvent.objects.get(provider=provider_key, event_id=event_id)
            created = False

        event = WebhookEvent.objects.select_for_update().get(pk=event.pk)

        if not created and event.processed_at is not None:
            return {
                "ok": True,
                "event_id": event.event_id,
                "status": event.status,
                "idempotent": True,
            }

        provider_reference = str(normalized.get("provider_reference") or "").strip()
        attempt_id = normalized.get("payment_attempt_id")

        attempt_qs = PaymentAttempt.objects.select_for_update().filter(provider=provider_key)
        payment_attempt = None
        if provider_reference:
            payment_attempt = attempt_qs.filter(provider_reference=provider_reference).first()
        if payment_attempt is None and attempt_id:
            payment_attempt = attempt_qs.filter(id=attempt_id).first()

        if payment_attempt is None:
            event.status = WebhookEvent.STATUS_IGNORED
            event.payload = payload
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "payload", "processed_at"])
            return {
                "ok": True,
                "event_id": event.event_id,
                "status": event.status,
                "idempotent": not created,
            }

        if payment_attempt.status in {PaymentAttempt.STATUS_PAID, PaymentAttempt.STATUS_FAILED}:
            event.status = WebhookEvent.STATUS_IGNORED
            event.payload = payload
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "payload", "processed_at"])
            return {
                "ok": True,
                "event_id": event.event_id,
                "status": event.status,
                "idempotent": True,
                "payment_attempt_id": payment_attempt.id,
            }

        paid = bool(normalized.get("paid"))
        failed = bool(normalized.get("failed"))

        if paid:
            payment_attempt.status = PaymentAttempt.STATUS_PAID
        elif failed:
            payment_attempt.status = PaymentAttempt.STATUS_FAILED
        else:
            event.status = WebhookEvent.STATUS_IGNORED
            event.payload = payload
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "payload", "processed_at"])
            return {
                "ok": True,
                "event_id": event.event_id,
                "status": event.status,
                "payment_attempt_id": payment_attempt.id,
            }

        payment_attempt.raw_response = payload
        payment_attempt.save(update_fields=["status", "raw_response", "updated_at"])

        if paid:
            process_successful_payment(payment_attempt.id)

        event.status = WebhookEvent.STATUS_PROCESSED
        event.payload = payload
        event.processed_at = timezone.now()
        event.save(update_fields=["status", "payload", "processed_at"])

        return {
            "ok": True,
            "event_id": event.event_id,
            "status": event.status,
            "payment_attempt_id": payment_attempt.id,
            "payment_status": payment_attempt.status,
            "idempotent": not created,
        }

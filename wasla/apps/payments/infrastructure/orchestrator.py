from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.conf import settings as django_settings
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
from apps.wallet.services.wallet_service import WalletService

logger = logging.getLogger(__name__)


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
        """Build standardized response."""
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
    def _is_retryable_error(cls, error_msg: str) -> bool:
        """Determine if error is retryable (transient failure)."""
        retryable_keywords = [
            "timeout",
            "connection",
            "network",
            "temporarily unavailable",
            "please retry",
            "service unavailable",
            "502",
            "503",
            "504",
        ]
        error_lower = str(error_msg).lower()
        return any(keyword in error_lower for keyword in retryable_keywords)

    @staticmethod
    def _schedule_retry(payment_attempt: PaymentAttempt) -> None:
        """Schedule payment retry with exponential backoff."""
        # Exponential backoff: 2^retry_count minutes
        retry_delay_minutes = 2 ** payment_attempt.retry_count
        
        next_retry = timezone.now() + timezone.timedelta(minutes=retry_delay_minutes)
        
        payment_attempt.retry_count += 1
        payment_attempt.last_retry_at = timezone.now()
        payment_attempt.next_retry_after = next_retry
        payment_attempt.retry_pending = True
        payment_attempt.status = PaymentAttempt.STATUS_RETRY_PENDING
        payment_attempt.save(
            update_fields=[
                "retry_count",
                "last_retry_at",
                "next_retry_after",
                "retry_pending",
                "status",
                "updated_at",
            ]
        )
        
        logger.info(
            "Payment retry scheduled",
            extra={
                "payment_attempt_id": payment_attempt.id,
                "retry_count": payment_attempt.retry_count,
                "next_retry_at": next_retry.isoformat(),
                "delay_minutes": retry_delay_minutes,
            },
        )

    @classmethod
    @transaction.atomic
    def retry_payment(cls, payment_attempt_id: int) -> dict[str, Any]:
        """Retry a failed payment creation."""
        payment_attempt = PaymentAttempt.objects.select_for_update().get(id=payment_attempt_id)
        
        if payment_attempt.status not in (
            PaymentAttempt.STATUS_RETRY_PENDING,
            PaymentAttempt.STATUS_FAILED,
        ):
            logger.warning(
                "Cannot retry payment in status",
                extra={
                    "payment_attempt_id": payment_attempt.id,
                    "status": payment_attempt.status,
                },
            )
            return cls._standard_response(ok=False, payment_attempt=payment_attempt)
        
        # Check if enough time has passed for retry
        if (
            payment_attempt.next_retry_after
            and timezone.now() < payment_attempt.next_retry_after
        ):
            logger.info(
                "Payment retry too soon",
                extra={
                    "payment_attempt_id": payment_attempt.id,
                    "next_retry_at": payment_attempt.next_retry_after.isoformat(),
                },
            )
            return cls._standard_response(ok=False, payment_attempt=payment_attempt)
        
        logger.info(
            "Retrying payment",
            extra={
                "payment_attempt_id": payment_attempt.id,
                "retry_count": payment_attempt.retry_count,
            },
        )
        
        # Clear retry status and attempt creation again
        payment_attempt.retry_pending = False
        payment_attempt.status = PaymentAttempt.STATUS_INITIATED
        payment_attempt.save(
            update_fields=["retry_pending", "status", "updated_at"]
        )
        
        # Recursively call create_payment to attempt again
        return cls.create_payment(payment_attempt)

    @classmethod
    @transaction.atomic
    def create_payment(cls, payment_attempt: PaymentAttempt) -> dict[str, Any]:
        """Create payment with idempotency protection and retry handling."""
        locked_attempt = PaymentAttempt.objects.select_for_update().get(pk=payment_attempt.pk)

        logger.info(
            "Creating payment",
            extra={
                "payment_attempt_id": locked_attempt.id,
                "provider": locked_attempt.provider,
                "amount": str(locked_attempt.amount),
                "currency": locked_attempt.currency,
                "idempotency_key": locked_attempt.idempotency_key,
                "retry_count": locked_attempt.retry_count,
            },
        )

        # Check for existing payment with same idempotency key (idempotent reuse)
        existing = (
            PaymentAttempt.objects.select_for_update()
            .filter(idempotency_key=locked_attempt.idempotency_key)
            .exclude(pk=locked_attempt.pk)
            .first()
        )
        if existing:
            logger.info(
                "Idempotent payment reuse detected",
                extra={
                    "payment_attempt_id": existing.id,
                    "idempotency_key": locked_attempt.idempotency_key,
                },
            )
            return cls._standard_response(
                ok=True,
                payment_attempt=existing,
                redirect_url=existing.raw_response.get("redirect_url", ""),
                idempotent_reuse=True,
                raw=existing.raw_response,
            )

        try:
            provider = cls._get_provider(locked_attempt)
            result = provider.create_payment(locked_attempt)

            if not result.get("ok"):
                # Check if error is retryable (transient failure)
                error_msg = result.get("error", "")
                is_retryable = cls._is_retryable_error(error_msg)

                logger.warning(
                    "Payment creation failed",
                    extra={
                        "payment_attempt_id": locked_attempt.id,
                        "error": error_msg,
                        "retryable": is_retryable,
                        "retry_count": locked_attempt.retry_count,
                    },
                )

                if is_retryable and locked_attempt.retry_count < (
                    getattr(django_settings, "PAYMENT_RETRY_MAX_ATTEMPTS", 3)
                ):
                    # Schedule retry with exponential backoff
                    cls._schedule_retry(locked_attempt)
                else:
                    locked_attempt.status = PaymentAttempt.STATUS_FAILED
                    locked_attempt.raw_response = result.get("raw", {})
                    locked_attempt.save(update_fields=["status", "raw_response", "updated_at"])

                return cls._standard_response(
                    ok=False,
                    payment_attempt=locked_attempt,
                    error=error_msg,
                    retryable=is_retryable,
                    raw=result.get("raw", {}),
                )

            # Success
            locked_attempt.provider_reference = result.get("provider_reference", "")
            locked_attempt.raw_response = result.get("raw", {})
            locked_attempt.status = PaymentAttempt.STATUS_PENDING
            locked_attempt.retry_count = 0
            locked_attempt.save(
                update_fields=[
                    "provider_reference",
                    "raw_response",
                    "status",
                    "retry_count",
                    "updated_at",
                ]
            )

            logger.info(
                "Payment created successfully",
                extra={
                    "payment_attempt_id": locked_attempt.id,
                    "provider_reference": result.get("provider_reference"),
                    "status": locked_attempt.status,
                },
            )

            return cls._standard_response(
                ok=True,
                payment_attempt=locked_attempt,
                redirect_url=result.get("redirect_url", ""),
                client_secret=result.get("client_secret", ""),
                raw=result.get("raw", {}),
            )

        except Exception as e:
            logger.exception(
                "Unexpected error during payment creation",
                extra={
                    "payment_attempt_id": locked_attempt.id,
                    "error": str(e),
                },
            )
            
            # Mark as failed due to system error
            locked_attempt.status = PaymentAttempt.STATUS_FAILED
            locked_attempt.raw_response = {"error": str(e)}
            locked_attempt.save(update_fields=["status", "raw_response", "updated_at"])
            
            return cls._standard_response(
                ok=False,
                payment_attempt=locked_attempt,
                error=f"System error: {str(e)}",
                raw={},
            )

    @classmethod
    @transaction.atomic
    def verify_payment(cls, payment_attempt: PaymentAttempt, data: dict[str, Any]) -> dict[str, Any]:
        """Verify payment status from callback data or webhook."""
        locked_attempt = PaymentAttempt.objects.select_for_update().get(pk=payment_attempt.pk)
        
        logger.info(
            "Verifying payment",
            extra={
                "payment_attempt_id": locked_attempt.id,
                "provider": locked_attempt.provider,
                "current_status": locked_attempt.status,
            },
        )
        
        try:
            provider = cls._get_provider(locked_attempt)
            result = provider.verify_payment(data)

            locked_attempt.provider_reference = (
                result.get("provider_reference") or locked_attempt.provider_reference
            )
            locked_attempt.raw_response = result.get("raw", {})
            
            old_status = locked_attempt.status
            locked_attempt.status = (
                PaymentAttempt.STATUS_CONFIRMED
                if bool(result.get("paid"))
                else PaymentAttempt.STATUS_FAILED
            )
            locked_attempt.save(
                update_fields=["provider_reference", "raw_response", "status", "updated_at"]
            )

            logger.info(
                "Payment verified",
                extra={
                    "payment_attempt_id": locked_attempt.id,
                    "old_status": old_status,
                    "new_status": locked_attempt.status,
                    "paid": bool(result.get("paid")),
                },
            )

            return cls._standard_response(
                ok=bool(result.get("paid")),
                payment_attempt=locked_attempt,
                paid=bool(result.get("paid")),
                raw=result.get("raw", {}),
            )
        except Exception as e:
            logger.exception(
                "Error verifying payment",
                extra={
                    "payment_attempt_id": locked_attempt.id,
                    "error": str(e),
                },
            )
            return cls._standard_response(
                ok=False,
                payment_attempt=locked_attempt,
                error=str(e),
            )

    @classmethod
    @transaction.atomic
    def refund(cls, payment_attempt: PaymentAttempt, amount: Decimal) -> dict[str, Any]:
        """Process refund for a payment."""
        locked_attempt = PaymentAttempt.objects.select_for_update().get(pk=payment_attempt.pk)
        
        logger.info(
            "Processing refund",
            extra={
                "payment_attempt_id": locked_attempt.id,
                "amount": str(amount),
                "currency": locked_attempt.currency,
                "provider": locked_attempt.provider,
                "provider_reference": locked_attempt.provider_reference,
            },
        )
        
        try:
            provider = cls._get_provider(locked_attempt)
            result = provider.refund(locked_attempt, amount)

            if bool(result.get("ok")):
                locked_attempt.status = PaymentAttempt.STATUS_REFUNDED
                locked_attempt.raw_response = result.get("raw", {})
                locked_attempt.provider_reference = (
                    result.get("provider_reference") or locked_attempt.provider_reference
                )
                locked_attempt.save(
                    update_fields=["status", "raw_response", "provider_reference", "updated_at"]
                )

                # Notify wallet service
                WalletService.on_refund(
                    store_id=locked_attempt.store_id,
                    tenant_id=getattr(locked_attempt.order, "tenant_id", None),
                    amount=amount,
                    reference=f"payment_attempt_refund:{locked_attempt.id}:{amount}",
                )

                logger.info(
                    "Refund processed successfully",
                    extra={
                        "payment_attempt_id": locked_attempt.id,
                        "refund_reference": result.get("provider_reference"),
                    },
                )
            else:
                logger.error(
                    "Refund failed",
                    extra={
                        "payment_attempt_id": locked_attempt.id,
                        "error": result.get("error"),
                    },
                )

            return cls._standard_response(
                ok=bool(result.get("ok")),
                payment_attempt=locked_attempt,
                refunded_amount=str(amount),
                error=result.get("error", ""),
                raw=result.get("raw", {}),
            )
        except Exception as e:
            logger.exception(
                "Unexpected error during refund",
                extra={
                    "payment_attempt_id": locked_attempt.id,
                    "error": str(e),
                },
            )
            return cls._standard_response(
                ok=False,
                payment_attempt=locked_attempt,
                error=f"Refund error: {str(e)}",
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
        """Process webhook event from payment provider."""
        provider_key = (provider or "").strip().lower()
        
        logger.info(
            "Processing webhook",
            extra={"provider": provider_key},
        )
        
        try:
            provider_impl = cls._get_provider_for_webhook(provider_key)
            normalized = provider_impl.parse_webhook(request)

            event_id = str(normalized.get("event_id") or "").strip()
            if not event_id:
                logger.warning("Webhook missing event_id", extra={"provider": provider_key})
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

            # Check for idempotency (already processed)
            if not created and event.processed_at is not None:
                logger.info(
                    "Webhook already processed (idempotent)",
                    extra={
                        "provider": provider_key,
                        "event_id": event_id,
                    },
                )
                return {
                    "ok": True,
                    "event_id": event.event_id,
                    "status": event.status,
                    "idempotent": True,
                }

            provider_reference = str(normalized.get("provider_reference") or "").strip()
            attempt_id = normalized.get("payment_attempt_id")
            store_id = normalized.get("store_id")

            logger.info(
                "Webhook parsed",
                extra={
                    "event_id": event_id,
                    "provider_reference": provider_reference,
                    "attempt_id": attempt_id,
                    "store_id": store_id,
                },
            )

            # Find affected payment attempt
            attempt_qs = PaymentAttempt.objects.select_for_update().filter(provider=provider_key)
            payment_attempt = None
            
            if provider_reference:
                payment_attempt = attempt_qs.filter(provider_reference=provider_reference).first()
            
            if payment_attempt is None and attempt_id:
                payment_attempt = attempt_qs.filter(id=attempt_id).first()

            if payment_attempt is None:
                logger.warning(
                    "Webhook payment attempt not found",
                    extra={
                        "event_id": event_id,
                        "provider_reference": provider_reference,
                        "attempt_id": attempt_id,
                    },
                )
                event.status = WebhookEvent.STATUS_IGNORED
                event.payload = payload
                event.processed_at = timezone.now()
                event.save(update_fields=["status", "payload", "processed_at"])
                return {
                    "ok": True,
                    "event_id": event.event_id,
                    "status": event.status,
                    "idempotent": not created,
                    "action": "ignored_payment_not_found",
                }

            # Skip if already processed
            if payment_attempt.status in {PaymentAttempt.STATUS_CONFIRMED, PaymentAttempt.STATUS_FAILED}:
                logger.info(
                    "Webhook for already-processed payment ignored",
                    extra={
                        "event_id": event_id,
                        "payment_attempt_id": payment_attempt.id,
                        "status": payment_attempt.status,
                    },
                )
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
                    "action": "ignored_already_processed",
                }

            # Determine payment outcome
            paid = bool(normalized.get("paid"))
            failed = bool(normalized.get("failed"))

            if not (paid or failed):
                logger.info(
                    "Webhook ignored (no success/failure status)",
                    extra={
                        "event_id": event_id,
                        "payment_attempt_id": payment_attempt.id,
                    },
                )
                event.status = WebhookEvent.STATUS_IGNORED
                event.payload = payload
                event.processed_at = timezone.now()
                event.save(update_fields=["status", "payload", "processed_at"])
                return {
                    "ok": True,
                    "event_id": event.event_id,
                    "status": event.status,
                    "payment_attempt_id": payment_attempt.id,
                    "action": "ignored_no_status_change",
                }

            # Update payment status
            old_status = payment_attempt.status
            if paid:
                payment_attempt.status = PaymentAttempt.STATUS_CONFIRMED
            elif failed:
                payment_attempt.status = PaymentAttempt.STATUS_FAILED

            payment_attempt.raw_response = payload
            payment_attempt.save(update_fields=["status", "raw_response", "updated_at"])

            logger.info(
                "Payment status updated from webhook",
                extra={
                    "event_id": event_id,
                    "payment_attempt_id": payment_attempt.id,
                    "old_status": old_status,
                    "new_status": payment_attempt.status,
                },
            )

            # Trigger settlement if payment succeeded
            if paid:
                logger.info(
                    "Processing successful payment",
                    extra={"payment_attempt_id": payment_attempt.id},
                )
                process_successful_payment(payment_attempt.id)

            # Mark event as processed
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
                "action": "payment_confirmed" if paid else "payment_failed",
            }
        except ValueError as e:
            logger.error("Invalid webhook", extra={"provider": provider_key, "error": str(e)})
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error processing webhook",
                extra={"provider": provider_key, "error": str(e)},
            )
            raise

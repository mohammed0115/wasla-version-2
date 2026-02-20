from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from django.utils.crypto import constant_time_compare

from apps.payments.models import PaymentAttempt, PaymentProviderSettings


class BasePaymentProvider(ABC):
    provider_code: str = ""

    def __init__(self, settings: PaymentProviderSettings):
        self.settings = settings

    @abstractmethod
    def create_payment(self, payment_attempt: PaymentAttempt) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def verify_payment(self, data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def refund(self, payment_attempt: PaymentAttempt, amount) -> dict[str, Any]:
        raise NotImplementedError

    def _extract_store_id(self, payload: dict[str, Any]) -> int | None:
        direct_keys = ("store_id", "store", "storeId")
        for key in direct_keys:
            value = payload.get(key)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    pass

        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        for key in direct_keys:
            value = metadata.get(key)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    pass

        return None

    def _resolve_webhook_secret(self, payload: dict[str, Any]) -> str:
        store_id = self._extract_store_id(payload)
        if store_id is not None:
            scoped = (
                PaymentProviderSettings.objects.filter(
                    provider=self.provider_code,
                    store_id=store_id,
                    is_active=True,
                )
                .exclude(webhook_secret="")
                .order_by("id")
                .first()
            )
            if scoped:
                return scoped.webhook_secret

        fallback = (
            PaymentProviderSettings.objects.filter(provider=self.provider_code, is_active=True)
            .exclude(webhook_secret="")
            .order_by("id")
            .first()
        )
        if fallback:
            return fallback.webhook_secret
        return ""

    def validate_webhook(self, request) -> bool:
        header_secret = (
            request.headers.get("X-WASLA-WEBHOOK-SECRET")
            or request.META.get("HTTP_X_WASLA_WEBHOOK_SECRET")
            or ""
        )
        if not header_secret:
            return False

        payload = request.data if isinstance(request.data, dict) else {}
        expected_secret = self._resolve_webhook_secret(payload)
        if not expected_secret:
            return False
        return constant_time_compare(str(header_secret), str(expected_secret))

    def parse_webhook(self, request) -> dict[str, Any]:
        payload = getattr(request, "data", None)
        if not isinstance(payload, dict):
            payload = {}
        status = str(payload.get("status", "")).lower()
        return {
            "event_id": str(payload.get("event_id") or payload.get("id") or ""),
            "provider_reference": str(
                payload.get("provider_reference")
                or payload.get("intent_reference")
                or payload.get("reference")
                or ""
            ),
            "payment_attempt_id": payload.get("payment_attempt_id"),
            "paid": status in {"paid", "succeeded", "captured", "completed", "success"},
            "failed": status in {"failed", "declined", "cancelled", "canceled", "error"},
            "raw": payload,
            # TODO: Replace this placeholder normalization with provider-native signed event mapping.
        }

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.payments.infrastructure.providers.base import BasePaymentProvider
from apps.payments.models import PaymentAttempt


class TapPaymentProvider(BasePaymentProvider):
    provider_code = "tap"

    def create_payment(self, payment_attempt: PaymentAttempt) -> dict[str, Any]:
        provider_reference = f"tap_{payment_attempt.id or payment_attempt.idempotency_key}"
        return {
            "redirect_url": f"/payments/redirect/tap/{payment_attempt.idempotency_key}",
            "provider_reference": provider_reference,
            "raw": {
                "provider": self.provider_code,
                "mode": self.settings.mode,
                "amount": str(payment_attempt.amount),
                "currency": payment_attempt.currency,
            },
        }

    def verify_payment(self, data: dict[str, Any]) -> dict[str, Any]:
        status = str(data.get("status", "")).lower()
        paid = status in {"paid", "captured", "succeeded", "success"}
        return {
            "paid": paid,
            "provider_reference": data.get("provider_reference") or data.get("id", ""),
            "raw": data,
        }

    def refund(self, payment_attempt: PaymentAttempt, amount: Decimal) -> dict[str, Any]:
        provider_reference = payment_attempt.provider_reference or f"tap_refund_{payment_attempt.id}"
        return {
            "ok": True,
            "provider_reference": provider_reference,
            "raw": {
                "provider": self.provider_code,
                "refunded_amount": str(amount),
                "currency": payment_attempt.currency,
            },
        }

    def validate_webhook(self, request) -> bool:
        # TODO: Replace with Tap signature verification algorithm (HMAC/signature headers).
        return super().validate_webhook(request)

    def parse_webhook(self, request) -> dict[str, Any]:
        payload = request.data if isinstance(request.data, dict) else {}
        status = str(payload.get("status", "")).lower()
        return {
            "event_id": str(payload.get("event_id") or payload.get("id") or ""),
            "provider_reference": str(
                payload.get("provider_reference")
                or payload.get("reference")
                or payload.get("payment_id")
                or ""
            ),
            "payment_attempt_id": payload.get("payment_attempt_id")
            or (payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}).get("payment_attempt_id"),
            "paid": status in {"captured", "paid", "succeeded", "success"},
            "failed": status in {"failed", "declined", "cancelled", "canceled", "error"},
            "raw": payload,
        }

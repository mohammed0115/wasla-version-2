from __future__ import annotations

from decimal import Decimal

from apps.payments.infrastructure.providers.base import BasePaymentProvider
from apps.payments.models import PaymentAttempt


class StripePaymentProvider(BasePaymentProvider):
    provider_code = "stripe"

    def create_payment(self, payment_attempt: PaymentAttempt) -> dict:
        provider_reference = f"pi_{payment_attempt.id or payment_attempt.idempotency_key}"
        return {
            "redirect_url": f"/payments/redirect/stripe/{payment_attempt.idempotency_key}",
            "provider_reference": provider_reference,
            "raw": {
                "provider": self.provider_code,
                "mode": self.settings.mode,
                "amount": str(payment_attempt.amount),
                "currency": payment_attempt.currency,
            },
        }

    def verify_payment(self, data: dict) -> dict:
        status = str(data.get("status", "")).lower()
        paid = status in {"succeeded", "paid", "success"}
        return {
            "paid": paid,
            "provider_reference": data.get("provider_reference") or data.get("payment_intent", ""),
            "raw": data,
        }

    def refund(self, payment_attempt: PaymentAttempt, amount: Decimal) -> dict:
        provider_reference = payment_attempt.provider_reference or f"re_{payment_attempt.id}"
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
        # TODO: Replace with Stripe-Signature verification against signed payload timestamp.
        return super().validate_webhook(request)

    def parse_webhook(self, request) -> dict:
        payload = request.data if isinstance(request.data, dict) else {}
        data_obj = payload.get("data", {}).get("object", {}) if isinstance(payload.get("data"), dict) else {}
        status = str(data_obj.get("status") or payload.get("status") or "").lower()
        metadata = data_obj.get("metadata", {}) if isinstance(data_obj.get("metadata"), dict) else {}
        return {
            "event_id": str(payload.get("id") or payload.get("event_id") or ""),
            "provider_reference": str(
                data_obj.get("id")
                or payload.get("provider_reference")
                or payload.get("payment_intent")
                or ""
            ),
            "payment_attempt_id": metadata.get("payment_attempt_id") or payload.get("payment_attempt_id"),
            "paid": status in {"succeeded", "paid", "success"},
            "failed": status in {"failed", "canceled", "cancelled", "requires_payment_method"},
            "raw": payload,
        }

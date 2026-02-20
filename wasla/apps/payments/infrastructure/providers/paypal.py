from __future__ import annotations

from decimal import Decimal

from apps.payments.infrastructure.providers.base import BasePaymentProvider
from apps.payments.models import PaymentAttempt


class PayPalPaymentProvider(BasePaymentProvider):
    provider_code = "paypal"

    def create_payment(self, payment_attempt: PaymentAttempt) -> dict:
        provider_reference = f"pp_{payment_attempt.id or payment_attempt.idempotency_key}"
        return {
            "redirect_url": f"/payments/redirect/paypal/{payment_attempt.idempotency_key}",
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
        paid = status in {"completed", "succeeded", "paid", "success"}
        return {
            "paid": paid,
            "provider_reference": data.get("provider_reference") or data.get("id", ""),
            "raw": data,
        }

    def refund(self, payment_attempt: PaymentAttempt, amount: Decimal) -> dict:
        provider_reference = payment_attempt.provider_reference or f"paypal_refund_{payment_attempt.id}"
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
        # TODO: Replace with PayPal transmission signature + cert verification.
        return super().validate_webhook(request)

    def parse_webhook(self, request) -> dict:
        payload = request.data if isinstance(request.data, dict) else {}
        resource = payload.get("resource", {}) if isinstance(payload.get("resource"), dict) else {}
        status = str(resource.get("status") or payload.get("status") or "").lower()
        custom_id = resource.get("custom_id")
        return {
            "event_id": str(payload.get("id") or payload.get("event_id") or ""),
            "provider_reference": str(
                resource.get("id")
                or payload.get("provider_reference")
                or payload.get("resource_id")
                or ""
            ),
            "payment_attempt_id": payload.get("payment_attempt_id") or custom_id,
            "paid": status in {"completed", "succeeded", "paid", "success"},
            "failed": status in {"failed", "denied", "voided", "canceled", "cancelled"},
            "raw": payload,
        }

"""Stripe Payment Gateway Provider."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
import os

from apps.payments.infrastructure.adapters.base import HostedPaymentAdapter
from apps.payments.models import PaymentProviderSettings
from apps.payments.domain.ports import PaymentRedirect, VerifiedEvent
from apps.payments.infrastructure.webhooks.signatures import verify_stripe_signature
from apps.payments.security.retry_logic import RetryableError


class StripeProvider(HostedPaymentAdapter):
    """
    Stripe payment provider.
    Supports: Cards, Apple Pay, Google Pay, International payments.
    
    API Base: https://api.stripe.com/v1
    Webhook validation: HMAC-SHA256
    """

    code = "stripe"
    name = "Stripe"
    payment_method = "card"
    default_base_url = "https://api.stripe.com/v1"

    def __init__(self, settings: PaymentProviderSettings):
        super().__init__(settings)
        self.api_key = self._resolve_env_value(
            self.credentials.get("api_key_env") or "STRIPE_API_KEY",
            self.credentials.get("api_key") or self.settings.secret_key,
        )
        self.webhook_secret = self._resolve_env_value(
            self.credentials.get("webhook_secret_env") or "STRIPE_WEBHOOK_SECRET",
            self.webhook_secret or self.settings.webhook_secret,
        )
        self.publishable_key = self._resolve_env_value(
            self.credentials.get("public_key_env") or "STRIPE_PUBLIC_KEY",
            self.credentials.get("public_key") or self.settings.public_key,
        )
        self.is_sandbox = bool(self.api_key) and not self.api_key.startswith("sk_live_")

    def initiate_payment(self, *, order, amount, currency, return_url: str) -> PaymentRedirect:
        """
        Create Stripe PaymentIntent.
        Amount in cents (100 cents = 1 unit).
        Returns client_secret for client-side confirmation.
        """
        if not self.api_key:
            raise ValueError("Stripe API key is missing. Configure STRIPE_API_KEY or api_key_env.")

        amount_cents = int(Decimal(amount) * 100)
        resolved_currency = (currency or "usd").lower()

        payload: dict[str, Any] = {
            "amount": amount_cents,
            "currency": resolved_currency,
            "payment_method_types[]": "card",
            "description": f"Order {order.order_number}",
            "receipt_email": order.customer_email or "",
            "metadata[order_id]": str(order.id),
            "metadata[order_number]": str(order.order_number),
            "metadata[store_id]": str(getattr(order, "store_id", "")),
            "metadata[tenant_id]": str(getattr(order, "tenant_id", "")),
        }

        idempotency_key = getattr(self, "idempotency_key", "") or ""
        data = self._post_stripe("/payment_intents", payload, idempotency_key=idempotency_key)

        intent_id = data.get("id", "")
        client_secret = data.get("client_secret", "")

        return PaymentRedirect(
            redirect_url="",
            client_secret=client_secret,
            provider_reference=intent_id,
        )

    def verify_callback(self, *, payload: dict, headers: dict, raw_body: str | None = None) -> VerifiedEvent:
        """
        Verify Stripe webhook.
        Validate signature and extract event type and payment intent.
        """
        raw = raw_body or ""
        signature = ""
        if headers:
            signature = headers.get("Stripe-Signature") or headers.get("stripe-signature") or ""

        tolerance = int(getattr(self.settings, "webhook_tolerance_seconds", 300) or 300)
        if not verify_stripe_signature(signature, secret=self.webhook_secret, payload=raw, tolerance_seconds=tolerance):
            raise ValueError("Invalid Stripe webhook signature")

        event_id = str(payload.get("id") or "")
        event_type = str(payload.get("type") or "")
        data = payload.get("data", {}).get("object", {}) if isinstance(payload.get("data"), dict) else {}

        if not event_id:
            raise ValueError("Stripe webhook missing event id")

        if event_type == "payment_intent.succeeded":
            intent_id = data.get("id", "")
            if not intent_id:
                raise ValueError("Stripe webhook missing payment intent id")
            return VerifiedEvent(
                event_id=event_id,
                event_type=event_type,
                intent_reference=str(intent_id),
                status="succeeded",
            )

        if event_type == "payment_intent.payment_failed":
            intent_id = data.get("id", "")
            if not intent_id:
                raise ValueError("Stripe webhook missing payment intent id")
            return VerifiedEvent(
                event_id=event_id,
                event_type=event_type,
                intent_reference=str(intent_id),
                status="failed",
            )

        raise ValueError(f"Unsupported Stripe event type: {event_type}")

    def _post_stripe(self, path: str, payload: dict[str, Any], *, idempotency_key: str = "") -> dict[str, Any]:
        """Post to Stripe API with form encoding."""
        import requests

        if not self.api_key:
            raise ValueError("Stripe API key is missing.")

        url = f"{self.base_url.rstrip('/')}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = str(idempotency_key)[:255]

        try:
            response = requests.post(url, data=payload, headers=headers, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise RetryableError(f"stripe_request_error: {exc}") from exc

        if response.status_code in {429, 500, 502, 503, 504}:
            raise RetryableError(f"stripe_transient_error:{response.status_code}")
        if response.status_code >= 400:
            raise ValueError(f"Stripe rejected request: {response.status_code} - {response.text}")

        return response.json() if response.content else {}

    def refund(self, *, payment_reference: str, amount: Decimal | None = None, reason: str | None = None) -> str:
        """Refund a Stripe payment."""
        payload: dict[str, Any] = {"metadata[reason]": reason or "Merchant refund"}
        if amount:
            payload["amount"] = int(amount * 100)

        data = self._post_stripe(f"/refunds", {"payment_intent": payment_reference, **payload})
        refund_id = data.get("id", "")
        status = data.get("status", "")

        return refund_id or status or "refunded"

    @staticmethod
    def _resolve_env_value(env_key: str, fallback: str | None = None) -> str:
        value = os.getenv(env_key) if env_key else None
        if value:
            return value
        return fallback or ""

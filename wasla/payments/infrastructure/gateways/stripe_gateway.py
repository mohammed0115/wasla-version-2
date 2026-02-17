"""Stripe Payment Gateway Provider."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from payments.infrastructure.adapters.base import HostedPaymentAdapter
from payments.models import PaymentProviderSettings
from payments.domain.ports import PaymentRedirect, VerifiedEvent


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

    def __init__(self, settings: PaymentProviderSettings):
        super().__init__(settings)
        # Stripe defaults
        if not self.base_url:
            self.base_url = "https://api.stripe.com/v1"
        self.api_key = self.credentials.get("api_key", "")
        self.is_sandbox = not self.api_key.startswith("sk_live_")

    def initiate_payment(self, *, order, amount, currency, return_url: str) -> PaymentRedirect:
        """
        Create payment intent on Stripe.
        Amount in cents (100 cents = 1 unit).
        Returns client secret for frontend handling or redirect.
        """
        amount_cents = int(amount * 100)

        payload: dict[str, Any] = {
            "amount": amount_cents,
            "currency": currency.lower(),
            "payment_method_types": ["card"],
            "customer_email": order.customer_email or "",
            "metadata": {
                "order_id": str(order.id),
                "order_number": order.order_number,
                "customer_name": order.customer_name or "",
            },
            "success_url": return_url,
            "cancel_url": return_url,
        }

        # Use Sessions API for hosted checkout
        data = self._post_stripe("/checkout/sessions", payload)
        
        session_id = data.get("id", "")
        url = data.get("url", "")

        return PaymentRedirect(
            redirect_url=url,
            client_secret=session_id,
            provider_reference=session_id,
        )

    def verify_callback(self, *, payload: dict, headers: dict, raw_body: str | None = None) -> VerifiedEvent:
        """
        Verify Stripe webhook.
        Validate signature and extract event type and session/payment intent.
        """
        raw = raw_body or ""
        signature = headers.get("stripe-signature", "")

        if not self._verify_stripe_signature(raw, signature):
            raise ValueError("Invalid Stripe webhook signature")

        event_type = payload.get("type", "")
        data = payload.get("data", {}).get("object", {})

        # Handle checkout.session.completed
        if event_type == "checkout.session.completed":
            session_id = data.get("id", "")
            payment_status = data.get("payment_status", "")
            status = "succeeded" if payment_status == "paid" else "pending"
            return VerifiedEvent(
                event_id=session_id,
                event_type="session",
                intent_reference=session_id,
                status=status,
            )

        # Handle payment_intent.succeeded/failed
        if event_type.startswith("payment_intent."):
            intent_id = data.get("id", "")
            intent_status = data.get("status", "")
            status_map = {
                "succeeded": "succeeded",
                "requires_payment_method": "pending",
                "requires_confirmation": "pending",
                "requires_action": "pending",
                "processing": "pending",
                "requires_capture": "pending",
                "canceled": "failed",
            }
            status = status_map.get(intent_status, "pending")
            return VerifiedEvent(
                event_id=intent_id,
                event_type="payment_intent",
                intent_reference=intent_id,
                status=status,
            )

        raise ValueError(f"Unsupported Stripe event type: {event_type}")

    def _post_stripe(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Post to Stripe API with form encoding."""
        import requests
        
        url = f"{self.base_url.rstrip('/')}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        try:
            response = requests.post(url, data=payload, headers=headers, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise ValueError(f"Stripe request failed: {exc}") from exc

        if response.status_code >= 400:
            raise ValueError(f"Stripe rejected request: {response.status_code} - {response.text}")

        return response.json() if response.content else {}

    def _verify_stripe_signature(self, raw_body: str, signature: str) -> bool:
        """Verify HMAC-SHA256 signature from Stripe."""
        import hmac
        import hashlib
        import time

        if not signature or not self.webhook_secret:
            return False

        try:
            # Stripe signature format: t=timestamp,v1=signature
            parts = {}
            for part in signature.split(","):
                key, value = part.split("=")
                parts[key] = value

            timestamp = parts.get("t")
            provided_sig = parts.get("v1")

            if not timestamp or not provided_sig:
                return False

            # Check if timestamp is recent (within 5 minutes)
            current_time = int(time.time())
            if abs(current_time - int(timestamp)) > 300:
                return False

            # Verify signature
            signed_content = f"{timestamp}.{raw_body}"
            expected_sig = hmac.new(
                self.webhook_secret.encode(),
                signed_content.encode(),
                hashlib.sha256,
            ).hexdigest()

            return hmac.compare_digest(provided_sig, expected_sig)
        except Exception:
            return False

    def refund(self, *, payment_reference: str, amount: Decimal | None = None, reason: str | None = None) -> str:
        """Refund a Stripe payment."""
        payload: dict[str, Any] = {
            "metadata[reason]": reason or "Merchant refund",
        }
        if amount:
            payload["amount"] = int(amount * 100)

        data = self._post_stripe(f"/refunds", {"payment_intent": payment_reference, **payload})
        refund_id = data.get("id", "")
        status = data.get("status", "")

        return refund_id or status or "refunded"

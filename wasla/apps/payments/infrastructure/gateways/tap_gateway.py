"""Tap Payment Gateway Provider (SAR focused, Mada/STC Pay/Card)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.payments.infrastructure.adapters.base import HostedPaymentAdapter
from apps.payments.models import PaymentProviderSettings
from apps.payments.domain.ports import PaymentRedirect, VerifiedEvent


class TapProvider(HostedPaymentAdapter):
    """
    Tap payment provider for Saudi Arabia.
    Supports: Mada, STC Pay, Debit/Credit cards.
    
    API Base: https://api.tap.company/v2
    Webhook validation: HMAC-SHA256
    """

    code = "tap"
    name = "Tap"
    payment_method = "card"

    def __init__(self, settings: PaymentProviderSettings):
        super().__init__(settings)
        # Tap defaults
        if not self.base_url:
            self.base_url = "https://api.tap.company/v2"
        if not self.initiate_path:
            self.initiate_path = "/charges"
        self.api_key = self.credentials.get("api_key", "")
        self.merchant_id = self.credentials.get("merchant_id", "")

    def initiate_payment(self, *, order, amount, currency, return_url: str) -> PaymentRedirect:
        """
        Create charge on Tap.
        Amount in fils (100 fils = 1 SAR).
        Returns redirect URL for hosted checkout.
        """
        amount_fils = int(amount * 100)  # Convert SAR to fils

        payload: dict[str, Any] = {
            "amount": amount_fils,
            "currency": currency,
            "merchant_id": self.merchant_id,
            "receipt": {
                "email": True,
                "sms": False,
            },
            "customer": {
                "first_name": order.customer_name.split()[0] if order.customer_name else "Customer",
                "email": order.customer_email or "",
                "phone": {
                    "country_code": "+966",
                    "number": order.customer_phone or "",
                },
            },
            "metadata": {
                "order_id": str(order.id),
                "order_number": order.order_number,
            },
            "redirect": {
                "url": return_url,
            },
        }

        data = self._post("/charges", payload)
        
        checkout_url = data.get("transaction", {}).get("url", "")
        charge_id = data.get("id", "")
        status = data.get("status", "")

        return PaymentRedirect(
            redirect_url=checkout_url or data.get("checkout_url", ""),
            client_secret=charge_id,
            provider_reference=charge_id,
        )

    def verify_callback(self, *, payload: dict, headers: dict, raw_body: str | None = None) -> VerifiedEvent:
        """
        Verify Tap webhook.
        Payload includes: type, data (charge details).
        """
        raw = raw_body or ""
        signature = headers.get("x-tap-signature", "")

        if not self._verify_tap_signature(raw, signature):
            raise ValueError("Invalid Tap webhook signature")

        event_type = payload.get("type", "")
        charge = payload.get("data", {})
        charge_id = charge.get("id", "")
        charge_status = charge.get("status", "")

        if not charge_id:
            raise ValueError("Invalid Tap webhook: missing charge ID")

        # Map Tap charge status to standard status
        status_map = {
            "CAPTURED": "succeeded",
            "AUTHORIZED": "succeeded",
            "FAILED": "failed",
            "DECLINED": "failed",
            "EXPIRED": "failed",
        }
        standard_status = status_map.get(charge_status.upper(), "pending")

        return VerifiedEvent(
            event_id=charge_id,
            event_type="charge",
            intent_reference=charge_id,
            status=standard_status,
        )

    def _verify_tap_signature(self, raw_body: str, signature: str) -> bool:
        """Verify HMAC-SHA256 signature from Tap."""
        import hmac
        import hashlib

        if not signature or not self.webhook_secret:
            return False

        expected = hmac.new(
            self.webhook_secret.encode(),
            raw_body.encode(),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected)

    def refund(self, *, payment_reference: str, amount: Decimal | None = None, reason: str | None = None) -> str:
        """Refund a Tap charge."""
        charge_id = payment_reference
        payload: dict[str, Any] = {}
        if amount:
            payload["amount"] = int(amount * 100)  # Convert to fils
        if reason:
            payload["reason"] = reason

        data = self._post(f"/charges/{charge_id}/refund", payload)
        refund_id = data.get("id", "")
        status = data.get("status", "")

        return refund_id or status or "refunded"

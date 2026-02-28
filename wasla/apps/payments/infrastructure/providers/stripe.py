from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import requests

from apps.payments.infrastructure.providers.base import BasePaymentProvider
from apps.payments.models import PaymentAttempt

logger = logging.getLogger(__name__)


class StripePaymentProvider(BasePaymentProvider):
    provider_code = "stripe"
    name = "Stripe"

    # Stripe API constants
    STRIPE_API_BASE = "https://api.stripe.com/v1"
    STRIPE_API_TIMEOUT = 30
    STRIPE_WEBHOOK_TOLERANCE = 300  # 5 minutes

    # Event type mappings
    EVENT_PAYMENT_INTENT_SUCCEEDED = "payment_intent.succeeded"
    EVENT_PAYMENT_INTENT_PAYMENT_FAILED = "payment_intent.payment_failed"
    EVENT_CHARGE_REFUNDED = "charge.refunded"

    def __init__(self, settings):
        super().__init__(settings)
        # Get API key from settings credentials dict
        api_key = settings.credentials.get("api_key")
        if not api_key:
            api_key = os.environ.get("STRIPE_API_KEY", "")
        
        if not api_key:
            raise ValueError("Stripe API key not configured in settings or STRIPE_API_KEY env var")
        
        self.api_key = api_key
        self.is_sandbox = api_key.startswith("sk_test_")
        
        # Get webhook signing secret
        webhook_secret = settings.webhook_secret or os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        self.webhook_secret = webhook_secret

    def create_payment(self, payment_attempt: PaymentAttempt) -> dict[str, Any]:
        """Create a Stripe PaymentIntent with idempotency key."""
        logger.info(
            "Creating Stripe PaymentIntent",
            extra={
                "payment_attempt_id": payment_attempt.id,
                "amount": str(payment_attempt.amount),
                "currency": payment_attempt.currency,
                "idempotency_key": payment_attempt.idempotency_key,
                "sandbox": self.is_sandbox,
            },
        )

        try:
            # Stripe amounts are in cents
            amount_cents = int(payment_attempt.amount * 100)
            
            payload = {
                "amount": amount_cents,
                "currency": payment_attempt.currency.lower(),
                "payment_method_types": ["card"],
                "metadata": {
                    "payment_attempt_id": str(payment_attempt.id or ""),
                    "store_id": str(payment_attempt.store_id),
                    "order_id": str(payment_attempt.order_id),
                    "idempotency_key": payment_attempt.idempotency_key,
                },
                "description": f"Payment for Order #{payment_attempt.order_id} - {payment_attempt.store.name}",
            }

            # Use idempotency key to prevent duplicates
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Idempotency-Key": payment_attempt.idempotency_key,
                "User-Agent": "Wasla-Payment-Service/1.0",
            }

            response = self._post("/payment_intents", payload, headers=headers)
            
            if "error" in response:
                logger.error(
                    "Stripe PaymentIntent creation failed",
                    extra={"error": response.get("error"), "payment_attempt_id": payment_attempt.id},
                )
                return {
                    "ok": False,
                    "error": response.get("error", {}).get("message", "Unknown error"),
                    "provider_reference": "",
                    "raw": response,
                }

            intent_id = response.get("id")
            client_secret = response.get("client_secret")

            logger.info(
                "Stripe PaymentIntent created successfully",
                extra={
                    "payment_attempt_id": payment_attempt.id,
                    "intent_id": intent_id,
                    "status": response.get("status"),
                },
            )

            return {
                "ok": True,
                "provider_reference": intent_id,
                "client_secret": client_secret,
                "redirect_url": "",  # Client will use client_secret to confirm payment
                "raw": response,
            }

        except requests.RequestException as e:
            logger.exception(
                "Stripe API request failed",
                extra={"payment_attempt_id": payment_attempt.id, "error": str(e)},
            )
            return {
                "ok": False,
                "error": f"Network error: {str(e)}",
                "provider_reference": "",
                "raw": {},
            }

    def verify_payment(self, data: dict[str, Any]) -> dict[str, Any]:
        """Verify payment status from webhook or callback data."""
        logger.debug("Verifying Stripe payment", extra={"data_keys": list(data.keys())})

        intent_id = data.get("provider_reference") or data.get("payment_intent") or data.get("id")
        status = str(data.get("status", "")).lower()
        
        paid = status in {"succeeded", "processing"}
        failed = status in {"requires_payment_method", "requires_action", "canceled"}

        return {
            "paid": paid,
            "failed": failed,
            "provider_reference": intent_id,
            "raw": data,
        }

    def refund(self, payment_attempt: PaymentAttempt, amount: Decimal) -> dict[str, Any]:
        """Refund a Stripe payment."""
        intent_id = payment_attempt.provider_reference
        if not intent_id:
            logger.error(
                "Cannot refund: no provider reference",
                extra={"payment_attempt_id": payment_attempt.id},
            )
            return {
                "ok": False,
                "error": "No provider reference found",
                "provider_reference": "",
                "raw": {},
            }

        logger.info(
            "Refunding Stripe payment",
            extra={
                "payment_attempt_id": payment_attempt.id,
                "intent_id": intent_id,
                "refund_amount": str(amount),
            },
        )

        try:
            # Stripe refunds are in cents
            amount_cents = int(amount * 100)
            
            payload = {
                "amount": amount_cents,
                "metadata": {
                    "payment_attempt_id": str(payment_attempt.id),
                    "store_id": str(payment_attempt.store_id),
                },
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Idempotency-Key": f"refund_{payment_attempt.id}_{int(time.time())}",
            }

            # Get the charge ID from the payment intent
            intent = self._get(f"/payment_intents/{intent_id}", headers=headers)
            charge_id = intent.get("charges", {}).get("data", [{}])[0].get("id")
            
            if not charge_id:
                logger.error(
                    "Cannot find charge ID for refund",
                    extra={"intent_id": intent_id},
                )
                return {
                    "ok": False,
                    "error": "No charge found for refund",
                    "provider_reference": "",
                    "raw": {},
                }

            # Create refund
            response = self._post(f"/charges/{charge_id}/refunds", payload, headers=headers)

            if "error" in response:
                logger.error(
                    "Stripe refund failed",
                    extra={"error": response.get("error"), "payment_attempt_id": payment_attempt.id},
                )
                return {
                    "ok": False,
                    "error": response.get("error", {}).get("message", "Refund failed"),
                    "provider_reference": "",
                    "raw": response,
                }

            refund_id = response.get("id")
            logger.info(
                "Stripe refund successful",
                extra={
                    "payment_attempt_id": payment_attempt.id,
                    "refund_id": refund_id,
                },
            )

            return {
                "ok": True,
                "provider_reference": refund_id,
                "raw": response,
            }

        except requests.RequestException as e:
            logger.exception(
                "Stripe refund request failed",
                extra={"payment_attempt_id": payment_attempt.id, "error": str(e)},
            )
            return {
                "ok": False,
                "error": f"Network error: {str(e)}",
                "provider_reference": "",
                "raw": {},
            }

    def validate_webhook(self, request) -> bool:
        """Validate Stripe webhook signature."""
        if not self.webhook_secret:
            logger.warning("Stripe webhook secret not configured")
            return False

        # Get signature from header
        sig_header = (
            request.headers.get("Stripe-Signature")
            or request.META.get("HTTP_STRIPE_SIGNATURE")
            or ""
        )
        
        if not sig_header:
            logger.warning("Missing Stripe-Signature header")
            return False

        # Get raw request body
        try:
            if hasattr(request, "body"):
                raw_body = request.body
            else:
                raw_body = request.stream.read()
                request.stream.seek(0)
        except Exception as e:
            logger.error(f"Failed to read request body: {e}")
            return False

        # Verify signature
        return self._verify_stripe_signature(raw_body, sig_header)

    def parse_webhook(self, request) -> dict[str, Any]:
        """Parse and normalize Stripe webhook event."""
        payload = request.data if isinstance(request.data, dict) else {}
        
        event_type = payload.get("type", "")
        event_id = payload.get("id", "")
        
        # Extract payment intent data
        data_obj = payload.get("data", {}).get("object", {})
        intent_id = data_obj.get("id", "")
        intent_status = str(data_obj.get("status", "")).lower()
        metadata = data_obj.get("metadata", {})

        # Determine success/failure based on event type
        paid = event_type == self.EVENT_PAYMENT_INTENT_SUCCEEDED
        failed = event_type == self.EVENT_PAYMENT_INTENT_PAYMENT_FAILED

        logger.info(
            "Parsed Stripe webhook",
            extra={
                "event_type": event_type,
                "event_id": event_id,
                "intent_id": intent_id,
                "status": intent_status,
                "paid": paid,
                "failed": failed,
            },
        )

        return {
            "event_id": event_id,
            "provider_reference": intent_id,
            "payment_attempt_id": metadata.get("payment_attempt_id"),
            "store_id": metadata.get("store_id"),
            "paid": paid,
            "failed": failed,
            "status": intent_status,
            "raw": payload,
        }

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Make POST request to Stripe API."""
        url = f"{self.STRIPE_API_BASE}{path}"
        
        if headers is None:
            headers = {}
        
        headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        })

        try:
            logger.debug(f"Stripe API POST: {path}")
            response = requests.post(
                url,
                data=urlencode(self._flatten_dict(payload)),
                headers=headers,
                timeout=self.STRIPE_API_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            logger.error(f"Stripe API error: {e.response.status_code} {e.response.text}")
            try:
                return e.response.json()
            except Exception:
                return {"error": {"message": str(e)}}

    def _get(
        self,
        path: str,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Make GET request to Stripe API."""
        url = f"{self.STRIPE_API_BASE}{path}"
        
        if headers is None:
            headers = {}
        
        headers.update({
            "Authorization": f"Bearer {self.api_key}",
        })

        try:
            logger.debug(f"Stripe API GET: {path}")
            response = requests.get(url, headers=headers, timeout=self.STRIPE_API_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Stripe API error: {str(e)}")
            return {"error": {"message": str(e)}}

    def _verify_stripe_signature(self, raw_body: bytes | str, sig_header: str) -> bool:
        """Verify Stripe webhook signature using HMAC-SHA256."""
        if isinstance(raw_body, str):
            raw_body = raw_body.encode("utf-8")

        try:
            # Parse signature header: t=timestamp,v1=signature
            timestamp = None
            signature = None
            
            for pair in sig_header.split(","):
                if pair.startswith("t="):
                    timestamp = int(pair[2:])
                elif pair.startswith("v1="):
                    signature = pair[3:]

            if not timestamp or not signature:
                logger.warning("Invalid Stripe-Signature format")
                return False

            # Check timestamp is within tolerance (prevent replay attacks)
            current_time = int(time.time())
            if abs(current_time - timestamp) > self.STRIPE_WEBHOOK_TOLERANCE:
                logger.warning(
                    f"Stripe webhook timestamp outside tolerance window: {current_time - timestamp}s"
                )
                return False

            # Compute expected signature
            signed_content = f"{timestamp}.{raw_body.decode('utf-8')}"
            expected_sig = hmac.new(
                self.webhook_secret.encode("utf-8"),
                signed_content.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            # Constant-time comparison to prevent timing attacks
            is_valid = hmac.compare_digest(signature, expected_sig)
            
            if not is_valid:
                logger.warning("Stripe webhook signature mismatch")
                return False

            logger.debug("Stripe webhook signature verified")
            return True

        except (ValueError, AttributeError) as e:
            logger.error(f"Error validating Stripe signature: {e}")
            return False

    @staticmethod
    def _flatten_dict(d: dict[str, Any], parent_key: str = "", sep: str = "[") -> dict[str, str]:
        """Flatten nested dict for Stripe API form encoding."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}]" if parent_key else k
            if isinstance(v, dict):
                items.extend(StripePaymentProvider._flatten_dict(v, new_key, sep).items())
            elif isinstance(v, (list, tuple)):
                for i, item in enumerate(v):
                    list_key = f"{new_key}[{i}]"
                    if isinstance(item, dict):
                        items.extend(StripePaymentProvider._flatten_dict(item, list_key, sep).items())
                    else:
                        items.append((list_key, str(item)))
            else:
                items.append((new_key, str(v)))
        return dict(items)

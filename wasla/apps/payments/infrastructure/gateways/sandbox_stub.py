from __future__ import annotations

import json
from uuid import uuid4

from apps.payments.domain.ports import PaymentRedirect, VerifiedEvent
from apps.payments.infrastructure.webhooks.signatures import (
    DEFAULT_SIGNATURE_HEADER,
    verify_hmac_signature,
)


class SandboxStubGateway:
    code = "sandbox"
    name = "Sandbox Stub"
    _default_secret = "sandbox-secret"

    def __init__(self, settings=None):
        self.settings = settings
        self.webhook_secret = (
            getattr(settings, "webhook_secret", "") or self._default_secret
        )
        if settings and getattr(settings, "credentials", None):
            header = settings.credentials.get("signature_header")
            self.signature_header = header or DEFAULT_SIGNATURE_HEADER
        else:
            self.signature_header = DEFAULT_SIGNATURE_HEADER

    def initiate_payment(self, *, order, amount, currency, return_url: str) -> PaymentRedirect:
        reference = f"SANDBOX-{uuid4().hex[:12]}"
        redirect_url = f"{return_url}?provider=sandbox&intent={reference}"
        return PaymentRedirect(redirect_url=redirect_url, client_secret=None, provider_reference=reference)

    def verify_callback(self, *, payload: dict, headers: dict, raw_body: str | None = None) -> VerifiedEvent:
        raw = raw_body or json.dumps(payload, separators=(",", ":"), sort_keys=True)
        signature = headers.get(self.signature_header) if headers else None
        if not verify_hmac_signature(signature or "", secret=self.webhook_secret, payload=raw):
            raise ValueError("Invalid signature.")
        event_id = payload.get("event_id") or ""
        intent_reference = payload.get("intent_reference") or ""
        status = payload.get("status") or "failed"
        if not event_id or not intent_reference:
            raise ValueError("Invalid payload.")
        return VerifiedEvent(event_id=event_id, event_type="payment", intent_reference=intent_reference, status=status)

    def refund(self, *, payment_reference: str, amount=None, reason: str | None = None) -> str:
        return "refunded"

    def create_intent(self, *, order, amount, currency, return_url: str) -> PaymentRedirect:
        return self.initiate_payment(order=order, amount=amount, currency=currency, return_url=return_url)

    def verify_event(self, *, payload: dict, headers: dict) -> VerifiedEvent:
        return self.verify_callback(payload=payload, headers=headers)

    def capture_or_confirm(self, *, intent_reference: str, event: VerifiedEvent | None = None) -> str:
        return "requires_action"

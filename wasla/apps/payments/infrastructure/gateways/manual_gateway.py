from __future__ import annotations

from uuid import uuid4

from apps.payments.domain.ports import PaymentRedirect, VerifiedEvent


class ManualGateway:
    code = "manual"
    name = "Manual Gateway"

    def __init__(self, settings=None):
        self.settings = settings

    def initiate_payment(self, *, order, amount, currency, return_url: str) -> PaymentRedirect:
        reference = f"MANUAL-{uuid4().hex[:12]}"
        return PaymentRedirect(redirect_url=return_url, client_secret=None, provider_reference=reference)

    def verify_callback(self, *, payload: dict, headers: dict, raw_body: str | None = None) -> VerifiedEvent:
        status_raw = str(payload.get("status") or payload.get("payment_status") or "").lower()
        if status_raw in {"paid", "succeeded", "success", "confirmed"}:
            status = "succeeded"
        elif status_raw in {"failed", "declined", "canceled", "cancelled"}:
            status = "failed"
        else:
            status = "pending"

        event_id = payload.get("event_id") or payload.get("id") or f"manual-{uuid4().hex[:12]}"
        intent_reference = payload.get("intent_reference") or payload.get("reference") or event_id

        return VerifiedEvent(
            event_id=str(event_id),
            event_type="manual",
            intent_reference=str(intent_reference),
            status=status,
        )

    def refund(self, *, payment_reference: str, amount=None, reason: str | None = None) -> str:
        return "refunded"

    # Compatibility aliases
    def create_payment(self, *, order, amount, currency, return_url: str) -> PaymentRedirect:
        return self.initiate_payment(order=order, amount=amount, currency=currency, return_url=return_url)

    def verify_payment(self, *, payload: dict, headers: dict, raw_body: str | None = None) -> VerifiedEvent:
        return self.verify_callback(payload=payload, headers=headers, raw_body=raw_body)

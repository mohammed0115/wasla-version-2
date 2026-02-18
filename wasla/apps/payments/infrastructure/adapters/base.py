from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import requests

from apps.payments.domain.ports import PaymentRedirect, VerifiedEvent
from apps.payments.infrastructure.webhooks.signatures import (
    DEFAULT_SIGNATURE_HEADER,
    verify_hmac_signature,
)
from apps.payments.models import PaymentProviderSettings


class HostedPaymentAdapter:
    code: str
    name: str
    payment_method: str
    scheme: str | None = None

    def __init__(self, settings: PaymentProviderSettings):
        if not settings:
            raise ValueError("Payment provider settings are required.")
        self.settings = settings
        self.credentials: dict[str, Any] = settings.credentials or {}
        self.base_url = self.credentials.get("api_base_url") or self.credentials.get("base_url") or ""
        if not self.base_url:
            raise ValueError(f"Provider '{self.code}' is missing api_base_url.")
        self.initiate_path = self.credentials.get("initiate_path", "/payments/initiate")
        self.refund_path = self.credentials.get("refund_path", "/payments/refund")
        self.timeout_seconds = int(self.credentials.get("timeout_seconds", 20))
        self.signature_header = self.credentials.get("signature_header") or DEFAULT_SIGNATURE_HEADER
        self.signature_encoding = self.credentials.get("signature_encoding", "hex")
        self.webhook_secret = (
            settings.webhook_secret
            or self.credentials.get("webhook_secret")
            or self.credentials.get("api_secret")
            or ""
        )
        self.field_map = self.credentials.get("field_map", {})
        self.response_fields = self.credentials.get("response_fields", {})
        self.status_map = self.credentials.get("status_map", {})

    def initiate_payment(self, *, order, amount, currency, return_url: str) -> PaymentRedirect:
        payload: dict[str, Any] = {
            "amount": str(amount),
            "currency": currency,
            "order_id": order.id,
            "order_number": getattr(order, "order_number", ""),
            "return_url": return_url,
            "payment_method": self.payment_method,
        }
        if self.scheme:
            payload["scheme"] = self.scheme
        merchant_id = self.credentials.get("merchant_id")
        if merchant_id:
            payload["merchant_id"] = merchant_id
        if self.credentials.get("initiate_payload"):
            extra = self.credentials.get("initiate_payload")
            if isinstance(extra, dict):
                payload.update(extra)

        data = self._post(self.initiate_path, payload)
        redirect_url = self._extract_response_value(
            data,
            "redirect_url",
            ["redirect_url", "redirectUrl", "payment_url", "url", "checkout_url"],
        )
        client_secret = self._extract_response_value(
            data,
            "client_secret",
            ["client_secret", "clientSecret", "token", "access_token"],
        )
        provider_reference = self._extract_response_value(
            data,
            "provider_reference",
            ["reference", "id", "payment_id", "transaction_id", "checkout_id"],
        )
        return PaymentRedirect(
            redirect_url=redirect_url,
            client_secret=client_secret,
            provider_reference=provider_reference,
        )

    def verify_callback(self, *, payload: dict, headers: dict, raw_body: str | None = None) -> VerifiedEvent:
        raw = raw_body or json.dumps(payload, separators=(",", ":"), sort_keys=True)
        signature = self._get_header(headers, self.signature_header)
        if not verify_hmac_signature(signature, secret=self.webhook_secret, payload=raw, encoding=self.signature_encoding):
            raise ValueError("Invalid signature.")

        event_id = self._extract_payload_value(payload, "event_id", ["event_id", "eventId", "id"])
        intent_reference = self._extract_payload_value(
            payload,
            "intent_reference",
            ["intent_reference", "intentReference", "reference", "payment_id", "transaction_id"],
        )
        status_raw = self._extract_payload_value(payload, "status", ["status", "payment_status", "state"])
        if not event_id or not intent_reference:
            raise ValueError("Invalid payload.")
        status = self._normalize_status(status_raw)
        return VerifiedEvent(
            event_id=str(event_id),
            event_type="payment",
            intent_reference=str(intent_reference),
            status=status,
        )

    def refund(self, *, payment_reference: str, amount: Decimal | None = None, reason: str | None = None) -> str:
        payload: dict[str, Any] = {"payment_reference": payment_reference}
        if amount is not None:
            payload["amount"] = str(amount)
        if reason:
            payload["reason"] = reason
        data = self._post(self.refund_path, payload)
        status = self._extract_response_value(
            data,
            "refund_status",
            ["refund_status", "status", "state"],
        )
        return str(status or "refunded")

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}{path}"
        headers = self._build_headers()
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise ValueError(f"Provider '{self.code}' request failed: {exc}") from exc
        if response.status_code >= 400:
            raise ValueError(f"Provider '{self.code}' rejected the request: {response.status_code}.")
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise ValueError("Provider response is not valid JSON.") from exc

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = self.credentials.get("api_key")
        auth_header = self.credentials.get("auth_header", "Authorization")
        auth_prefix = self.credentials.get("auth_prefix", "Bearer")
        if api_key:
            headers[auth_header] = f"{auth_prefix} {api_key}".strip()
        extra_headers = self.credentials.get("headers")
        if isinstance(extra_headers, dict):
            for key, value in extra_headers.items():
                headers[str(key)] = str(value)
        return headers

    def _extract_payload_value(self, payload: dict, logical_key: str, fallback_keys: list[str]) -> Any:
        mapped = self.field_map.get(logical_key)
        if mapped:
            return payload.get(mapped)
        for key in fallback_keys:
            if key in payload:
                return payload.get(key)
        return None

    def _extract_response_value(self, payload: dict, logical_key: str, fallback_keys: list[str]) -> Any:
        mapped = self.response_fields.get(logical_key)
        if mapped:
            return payload.get(mapped)
        for key in fallback_keys:
            if key in payload:
                return payload.get(key)
        return None

    def _normalize_status(self, status_value: Any) -> str:
        if status_value is None:
            return "failed"
        status = str(status_value).strip().lower()
        if status in self.status_map:
            return str(self.status_map[status])
        if status in {"success", "succeeded", "paid", "captured", "approved"}:
            return "succeeded"
        if status in {"failed", "declined", "canceled", "cancelled", "expired"}:
            return "failed"
        if status in {"pending", "authorized", "requires_action", "processing"}:
            return "pending"
        return status

    @staticmethod
    def _get_header(headers: dict, name: str) -> str:
        if not headers:
            return ""
        target = name.lower()
        for key, value in headers.items():
            if str(key).lower() == target:
                return str(value)
        return ""

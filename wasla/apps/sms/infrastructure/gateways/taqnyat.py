from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

import requests

from apps.sms.domain.entities import SmsDeliveryResult, SmsMessage
from apps.sms.domain.errors import SmsConfigurationError, SmsGatewayError


class TaqnyatSmsGateway:
    name = "taqnyat"
    supports_scheduling = True

    def __init__(
        self,
        *,
        bearer_token: str,
        base_url: str = "https://api.taqnyat.sa",
        timeout_seconds: int = 10,
        include_bearer_as_query_param: bool = False,
    ) -> None:
        self._bearer_token = (bearer_token or "").strip()
        if not self._bearer_token:
            raise SmsConfigurationError("Taqnyat bearer token is not configured.")
        self._base_url = (base_url or "https://api.taqnyat.sa").rstrip("/")
        self._timeout_seconds = int(timeout_seconds or 10)
        self._include_bearer_as_query_param = bool(include_bearer_as_query_param)

    def send(self, message: SmsMessage) -> SmsDeliveryResult:
        url = f"{self._base_url}/v1/messages"

        recipients = [recipient.lstrip("+") for recipient in message.recipients]
        payload: dict[str, Any] = {
            "recipients": recipients,
            "body": message.body,
            "sender": message.sender,
        }

        if message.scheduled_at is not None:
            payload["scheduledDatetime"] = self._format_scheduled_datetime(message.scheduled_at)

        headers = {
            "Authorization": f"Bearer {self._bearer_token}",
            "Accept": "application/json",
        }
        params = {"bearerTokens": self._bearer_token} if self._include_bearer_as_query_param else None

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                params=params,
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            raise SmsGatewayError(str(exc), provider=self.name) from exc

        raw: dict[str, Any] | None
        try:
            raw = response.json()
        except ValueError:
            raw = {"text": (response.text or "")[:2000]}

        if response.status_code not in (200, 201):
            message_text = ""
            if isinstance(raw, dict):
                message_text = str(raw.get("message") or raw.get("error") or "")
            raise SmsGatewayError(
                f"Taqnyat send failed ({response.status_code}) {message_text}".strip(),
                provider=self.name,
                status_code=response.status_code,
            )

        provider_message_id = None
        if isinstance(raw, dict):
            provider_message_id = str(raw.get("messageId") or raw.get("message_id") or "") or None

        status = "scheduled" if message.scheduled_at is not None else "queued"
        return SmsDeliveryResult(
            provider=self.name,
            status=status,  # type: ignore[arg-type]
            provider_message_id=provider_message_id,
            raw={"request": asdict(message), "response": raw},
        )

    @staticmethod
    def _format_scheduled_datetime(value: datetime) -> str:
        # Taqnyat expects: YYYY-MM-DDTHH:MM
        return value.strftime("%Y-%m-%dT%H:%M")


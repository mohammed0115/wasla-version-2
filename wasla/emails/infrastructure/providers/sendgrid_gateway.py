from __future__ import annotations

from typing import Any

import requests

from emails.domain.ports import EmailGatewayPort
from emails.domain.types import EmailMessage, EmailSendResult


class SendGridEmailGateway(EmailGatewayPort):
    def __init__(self, *, api_key: str, from_email: str, from_name: str = ""):
        self._api_key = api_key
        self._from_email = from_email
        self._from_name = from_name

    def send(self, *, message: EmailMessage) -> EmailSendResult:
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        payload: dict[str, Any] = {
            "personalizations": [{"to": [{"email": message.to_email}]}],
            "from": {"email": self._from_email, **({"name": self._from_name} if self._from_name else {})},
            "subject": message.subject,
            "content": [],
        }
        if message.text:
            payload["content"].append({"type": "text/plain", "value": message.text})
        if message.html:
            payload["content"].append({"type": "text/html", "value": message.html})

        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code not in (200, 202):
            raise RuntimeError(f"SendGrid send failed: status={r.status_code}, body={r.text[:800]}")
        provider_id = r.headers.get("X-Message-Id", "") or r.headers.get("x-message-id", "")
        return EmailSendResult(provider_message_id=provider_id or "")


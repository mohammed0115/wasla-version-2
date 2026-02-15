from __future__ import annotations

from typing import Any

import requests

from emails.domain.ports import EmailGatewayPort
from emails.domain.types import EmailMessage, EmailSendResult


class MailgunEmailGateway(EmailGatewayPort):
    def __init__(self, *, api_key: str, domain: str, base_url: str, from_email: str, from_name: str = ""):
        self._api_key = api_key
        self._domain = domain
        self._base_url = base_url.rstrip("/")
        self._from_email = from_email
        self._from_name = from_name

    def send(self, *, message: EmailMessage) -> EmailSendResult:
        url = f"{self._base_url}/v3/{self._domain}/messages"
        from_header = self._from_email
        if self._from_name:
            from_header = f"{self._from_name} <{self._from_email}>"

        data: dict[str, Any] = {
            "from": from_header,
            "to": message.to_email,
            "subject": message.subject,
        }
        if message.text:
            data["text"] = message.text
        if message.html:
            data["html"] = message.html

        r = requests.post(url, auth=("api", self._api_key), data=data, timeout=15)
        if r.status_code not in (200, 202):
            raise RuntimeError(f"Mailgun send failed: status={r.status_code}, body={r.text[:800]}")

        # Mailgun returns JSON with id/message
        try:
            payload = r.json()
        except Exception:
            payload = {}
        provider_id = (payload.get("id") or "").strip("<>").strip()
        return EmailSendResult(provider_message_id=provider_id or "")


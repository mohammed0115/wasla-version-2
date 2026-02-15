from __future__ import annotations

"""
SMTP email gateway adapter.

AR: يدعم TLS (STARTTLS) أو SSL (SMTP_SSL) حسب الإعدادات.
EN: Supports either TLS (STARTTLS) or SSL (SMTP_SSL) based on configuration.
"""

import smtplib
from email.message import EmailMessage

from notifications.domain.errors import EmailGatewayError
from notifications.domain.ports import EmailGateway


class SmtpEmailGateway(EmailGateway):
    """Send email via SMTP (optionally SSL/TLS)."""

    name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = True,
        use_ssl: bool = False,
    ) -> None:
        self._host = host
        self._port = int(port)
        self._username = username
        self._password = password
        self._use_tls = bool(use_tls)
        self._use_ssl = bool(use_ssl)

    def send_email(self, *, subject: str, body: str, to_email: str, from_email: str) -> None:
        try:
            msg = EmailMessage()
            msg["From"] = from_email
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.set_content(body)

            if self._use_ssl:
                server_context = smtplib.SMTP_SSL(self._host, self._port)
            else:
                server_context = smtplib.SMTP(self._host, self._port)
            with server_context as server:
                if self._use_tls and not self._use_ssl:
                    server.starttls()
                if self._username and self._password:
                    server.login(self._username, self._password)
                server.send_message(msg)
        except Exception as exc:  # pragma: no cover - network errors vary
            raise EmailGatewayError(str(exc)) from exc

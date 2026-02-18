from __future__ import annotations

import uuid

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

from apps.emails.domain.ports import EmailGatewayPort
from apps.emails.domain.types import EmailMessage, EmailSendResult


class SmtpEmailGateway(EmailGatewayPort):
    def __init__(
        self,
        *,
        from_email: str,
        from_name: str = "",
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool | None = None,
        use_ssl: bool | None = None,
        timeout: int | None = None,
    ):
        self._from_email = from_email
        self._from_name = from_name
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._use_ssl = use_ssl
        self._timeout = timeout

    def send(self, *, message: EmailMessage) -> EmailSendResult:
        from_header = self._from_email
        if self._from_name:
            from_header = f"{self._from_name} <{self._from_email}>"

        connection = None
        connection_kwargs = {
            "host": self._host,
            "port": self._port,
            "username": self._username,
            "password": self._password,
            "timeout": self._timeout,
        }
        connection_kwargs = {k: v for k, v in connection_kwargs.items() if v is not None}
        if self._use_tls is not None:
            connection_kwargs["use_tls"] = bool(self._use_tls)
        if self._use_ssl is not None:
            connection_kwargs["use_ssl"] = bool(self._use_ssl)
        backend = getattr(settings, "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
        if connection_kwargs:
            connection = get_connection(backend=backend, **connection_kwargs)
        else:
            connection = get_connection(backend=backend)

        email = EmailMultiAlternatives(
            subject=message.subject,
            body=message.text or "",
            from_email=from_header,
            to=[message.to_email],
            headers=dict(message.headers or {}),
            connection=connection,
        )
        if message.html:
            email.attach_alternative(message.html, "text/html")
        email.send(fail_silently=False)
        return EmailSendResult(provider_message_id=str(uuid.uuid4()))

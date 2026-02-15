from __future__ import annotations

from notifications.domain.ports import EmailGateway


class ConsoleEmailGateway(EmailGateway):
    name = "console"

    def send_email(self, *, subject: str, body: str, to_email: str, from_email: str) -> None:
        # Intentionally no-op: used for dev/test.
        _ = (subject, body, to_email, from_email)


from __future__ import annotations

from dataclasses import dataclass

from notifications.domain.policies import validate_body, validate_email_address, validate_subject
from notifications.infrastructure.router import EmailGatewayRouter


@dataclass(frozen=True)
class SendEmailCommand:
    subject: str
    body: str
    to_email: str
    from_email: str | None = None


class SendEmailUseCase:
    @staticmethod
    def execute(cmd: SendEmailCommand) -> None:
        subject = validate_subject(cmd.subject)
        body = validate_body(cmd.body)
        to_email = validate_email_address(cmd.to_email)

        resolved = EmailGatewayRouter.resolve()
        from_email = cmd.from_email or resolved.default_from_email

        resolved.gateway.send_email(
            subject=subject,
            body=body,
            to_email=to_email,
            from_email=from_email,
        )


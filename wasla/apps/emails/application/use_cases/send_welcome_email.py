from __future__ import annotations

from dataclasses import dataclass

from apps.emails.application.use_cases.send_email import SendEmailCommand, SendEmailUseCase


@dataclass(frozen=True)
class SendWelcomeEmailCommand:
    tenant_id: int
    to_email: str
    full_name: str = ""


class SendWelcomeEmailUseCase:
    TEMPLATE_KEY = "welcome"

    @staticmethod
    def execute(cmd: SendWelcomeEmailCommand):
        return SendEmailUseCase.execute(
            SendEmailCommand(
                tenant_id=cmd.tenant_id,
                to_email=cmd.to_email,
                template_key=SendWelcomeEmailUseCase.TEMPLATE_KEY,
                context={"full_name": cmd.full_name},
                idempotency_key=f"welcome:{cmd.tenant_id}:{cmd.to_email}".lower(),
                metadata={"event": "welcome"},
            )
        )


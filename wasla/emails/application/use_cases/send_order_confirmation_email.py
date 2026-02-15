from __future__ import annotations

from dataclasses import dataclass

from emails.application.use_cases.send_email import SendEmailCommand, SendEmailUseCase


@dataclass(frozen=True)
class SendOrderConfirmationEmailCommand:
    tenant_id: int
    to_email: str
    order_number: str
    total_amount: str


class SendOrderConfirmationEmailUseCase:
    TEMPLATE_KEY = "order_confirmation"

    @staticmethod
    def execute(cmd: SendOrderConfirmationEmailCommand):
        return SendEmailUseCase.execute(
            SendEmailCommand(
                tenant_id=cmd.tenant_id,
                to_email=cmd.to_email,
                template_key=SendOrderConfirmationEmailUseCase.TEMPLATE_KEY,
                context={"order_number": cmd.order_number, "total_amount": cmd.total_amount},
                idempotency_key=f"order_confirmation:{cmd.tenant_id}:{cmd.order_number}".lower(),
                metadata={"event": "order_confirmation", "order_number": cmd.order_number},
            )
        )


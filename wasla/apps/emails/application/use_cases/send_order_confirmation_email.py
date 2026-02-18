from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from apps.emails.application.use_cases.send_email import SendEmailCommand, SendEmailUseCase


@dataclass(frozen=True)
class SendOrderConfirmationEmailCommand:
    tenant_id: int
    to_email: str
    order_number: str
    total_amount: str
    customer_name: Optional[str] = None
    shipping_address: Optional[dict] = None


class SendOrderConfirmationEmailUseCase:
    TEMPLATE_KEY = "order_confirmation"

    @staticmethod
    def execute(cmd: SendOrderConfirmationEmailCommand):
        context = {
            "order_number": cmd.order_number,
            "total_amount": cmd.total_amount,
            "customer_name": cmd.customer_name or "Valued Customer",
            "shipping_address": cmd.shipping_address or {},
        }
        return SendEmailUseCase.execute(
            SendEmailCommand(
                tenant_id=cmd.tenant_id,
                to_email=cmd.to_email,
                template_key=SendOrderConfirmationEmailUseCase.TEMPLATE_KEY,
                context=context,
                idempotency_key=f"order_confirmation:{cmd.tenant_id}:{cmd.order_number}".lower(),
                metadata={"event": "order_confirmation", "order_number": cmd.order_number},
            )
        )


@dataclass(frozen=True)
class SendOrderShippedEmailCommand:
    tenant_id: int
    to_email: str
    order_number: str
    tracking_number: str
    customer_name: Optional[str] = None
    carrier_name: Optional[str] = None


class SendOrderShippedEmailUseCase:
    TEMPLATE_KEY = "order_shipped"

    @staticmethod
    def execute(cmd: SendOrderShippedEmailCommand):
        context = {
            "order_number": cmd.order_number,
            "tracking_number": cmd.tracking_number,
            "customer_name": cmd.customer_name or "Valued Customer",
            "carrier_name": cmd.carrier_name or "Courier",
        }
        return SendEmailUseCase.execute(
            SendEmailCommand(
                tenant_id=cmd.tenant_id,
                to_email=cmd.to_email,
                template_key=SendOrderShippedEmailUseCase.TEMPLATE_KEY,
                context=context,
                idempotency_key=f"order_shipped:{cmd.tenant_id}:{cmd.order_number}".lower(),
                metadata={"event": "order_shipped", "order_number": cmd.order_number},
            )
        )


@dataclass(frozen=True)
class SendOrderDeliveredEmailCommand:
    tenant_id: int
    to_email: str
    order_number: str
    customer_name: Optional[str] = None


class SendOrderDeliveredEmailUseCase:
    TEMPLATE_KEY = "order_delivered"

    @staticmethod
    def execute(cmd: SendOrderDeliveredEmailCommand):
        context = {
            "order_number": cmd.order_number,
            "customer_name": cmd.customer_name or "Valued Customer",
        }
        return SendEmailUseCase.execute(
            SendEmailCommand(
                tenant_id=cmd.tenant_id,
                to_email=cmd.to_email,
                template_key=SendOrderDeliveredEmailUseCase.TEMPLATE_KEY,
                context=context,
                idempotency_key=f"order_delivered:{cmd.tenant_id}:{cmd.order_number}".lower(),
                metadata={"event": "order_delivered", "order_number": cmd.order_number},
            )
        )


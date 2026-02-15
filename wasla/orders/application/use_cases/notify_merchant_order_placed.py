from __future__ import annotations

from dataclasses import dataclass

from emails.application.use_cases.send_order_confirmation_email import (
    SendOrderConfirmationEmailCommand,
    SendOrderConfirmationEmailUseCase,
)
from orders.models import Order
from tenants.models import StoreProfile


@dataclass(frozen=True)
class NotifyMerchantOrderPlacedCommand:
    order_id: int
    tenant_id: int


class NotifyMerchantOrderPlacedUseCase:
    @staticmethod
    def execute(cmd: NotifyMerchantOrderPlacedCommand):
        order = Order.objects.filter(id=cmd.order_id, store_id=cmd.tenant_id).first()
        if not order:
            return None
        profile = StoreProfile.objects.filter(tenant_id=cmd.tenant_id).select_related("owner").first()
        owner = getattr(profile, "owner", None)
        to_email = (getattr(owner, "email", "") or "").strip()
        if not to_email:
            return None
        return SendOrderConfirmationEmailUseCase.execute(
            SendOrderConfirmationEmailCommand(
                tenant_id=cmd.tenant_id,
                to_email=to_email,
                order_number=order.order_number,
                total_amount=str(order.total_amount),
            )
        )

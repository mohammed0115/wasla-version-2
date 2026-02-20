from __future__ import annotations

from dataclasses import dataclass

from apps.emails.application.use_cases.send_order_confirmation_email import (
    SendOrderConfirmationEmailCommand,
    SendOrderConfirmationEmailUseCase,
)
from apps.orders.models import Order
from apps.tenants.models import StoreProfile


@dataclass(frozen=True)
class NotifyMerchantOrderPlacedCommand:
    order_id: int
    tenant_id: int


class NotifyMerchantOrderPlacedUseCase:
    @staticmethod
    def execute(cmd: NotifyMerchantOrderPlacedCommand):
        order = Order.objects.for_tenant(cmd.tenant_id).filter(id=cmd.order_id).first()
        if not order:
            return None
        resolved_tenant_id = order.tenant_id or cmd.tenant_id
        profile = StoreProfile.objects.filter(tenant_id=resolved_tenant_id).select_related("owner").first()
        owner = getattr(profile, "owner", None)
        to_email = (getattr(owner, "email", "") or "").strip()
        if not to_email:
            return None
        return SendOrderConfirmationEmailUseCase.execute(
            SendOrderConfirmationEmailCommand(
                tenant_id=resolved_tenant_id,
                to_email=to_email,
                order_number=order.order_number,
                total_amount=str(order.total_amount),
            )
        )

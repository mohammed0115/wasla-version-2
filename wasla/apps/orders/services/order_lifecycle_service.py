from __future__ import annotations

from django.db import transaction

from apps.wallet.services.wallet_service import WalletService

from ..models import Order


class OrderLifecycleService:
    ORDER_TRANSITIONS: dict[str, list[str]] = {
        "pending": ["paid", "cancelled"],
        "paid": ["processing"],
        "processing": ["shipped"],
        "shipped": ["delivered"],
        "delivered": ["completed"],
        "completed": [],
        "cancelled": [],
    }

    @classmethod
    def allowed_transitions(cls, current_status: str) -> list[str]:
        return list(cls.ORDER_TRANSITIONS.get(current_status, []))

    @staticmethod
    @transaction.atomic
    def transition(*, order: Order, new_status: str) -> Order:
        resolved_new_status = (new_status or "").strip()
        allowed = OrderLifecycleService.allowed_transitions(order.status)

        if resolved_new_status not in allowed:
            raise ValueError("Invalid status transition.")

        if resolved_new_status in {"delivered", "completed"} and not order.shipments.exists():
            raise ValueError("Cannot mark delivered/completed without a shipment.")

        order.status = resolved_new_status
        order.save(update_fields=["status"])

        if resolved_new_status == "delivered":
            order.shipments.exclude(status__in=["delivered", "cancelled"]).update(status="delivered")
            WalletService.on_order_delivered(
                store_id=order.store_id,
                tenant_id=order.tenant_id,
                net_amount=order.total_amount,
                reference=f"order_delivered:{order.id}",
            )

        if resolved_new_status == "completed":
            try:
                WalletService.on_order_delivered(
                    store_id=order.store_id,
                    tenant_id=order.tenant_id,
                    net_amount=order.total_amount,
                    reference=f"order_delivered:{order.id}",
                )
            except ValueError:
                pass

        return order

from __future__ import annotations

from django.db import transaction

from apps.wallet.services.wallet_service import WalletService

from ..models import Order


class OrderLifecycleService:
    """
    Enhanced order lifecycle with production commerce states.
    
    State diagram:
    pending → paid → processing → shipped → delivered → completed
                                                     ↘ returned → partially_refunded/refunded
                                                     
    Can also move to cancelled from: pending, paid
    Can move to returned from: delivered (within return window)
    """
    
    ORDER_TRANSITIONS: dict[str, list[str]] = {
        # Core flow
        "pending": ["paid", "cancelled"],
        "paid": ["processing"],
        "processing": ["shipped"],
        "shipped": ["delivered"],
        "delivered": ["completed", "returned"],  # Can be returned within window
        "completed": ["returned"],  # Can still be returned
        
        # Return & Refund flow
        "returned": ["partially_refunded", "refunded"],
        "partially_refunded": ["refunded"],  # Can refund additional amounts
        "refunded": [],  # Terminal state
        
        # Terminal states
        "cancelled": [],
    }

    @classmethod
    def allowed_transitions(cls, current_status: str) -> list[str]:
        return list(cls.ORDER_TRANSITIONS.get(current_status, []))

    @staticmethod
    @transaction.atomic
    def transition(*, order: Order, new_status: str) -> Order:
        """
        Transition order to new status.
        
        Args:
            order: The Order to transition
            new_status: Target status
            
        Returns:
            Updated Order instance
            
        Raises:
            ValueError: If transition is invalid
        """
        resolved_new_status = (new_status or "").strip()
        allowed = OrderLifecycleService.allowed_transitions(order.status)

        if resolved_new_status not in allowed:
            raise ValueError(
                f"Invalid status transition from {order.status} to {resolved_new_status}. "
                f"Allowed: {', '.join(allowed)}"
            )

        if resolved_new_status in {"delivered", "completed"} and not order.shipments.exists():
            raise ValueError("Cannot mark delivered/completed without a shipment.")

        # Update order status
        order.status = resolved_new_status
        order.save(update_fields=["status"])

        # Handle state-specific logic
        if resolved_new_status == "delivered":
            order.shipments.exclude(status__in=["delivered", "cancelled"]).update(status="delivered")
            WalletService.on_order_delivered(
                store_id=order.store_id,
                tenant_id=order.tenant_id,
                net_amount=order.total_amount,
                reference=f"order_delivered:{order.id}",
            )

        elif resolved_new_status == "completed":
            try:
                WalletService.on_order_delivered(
                    store_id=order.store_id,
                    tenant_id=order.tenant_id,
                    net_amount=order.total_amount,
                    reference=f"order_completed:{order.id}",
                )
            except ValueError:
                pass

        elif resolved_new_status == "returned":
            # RMA initiated - wallet funds may be held pending refund approval
            pass

        elif resolved_new_status in {"partially_refunded", "refunded"}:
            # Refund processed - reverse wallet entry if needed
            pass

        elif resolved_new_status == "cancelled":
            # Return stock reservations and release wallet holds
            OrderLifecycleService._handle_cancellation(order)

        return order

    @staticmethod
    def _handle_cancellation(order: Order) -> None:
        """
        Handle order cancellation: release stock, wallet holds, etc.
        
        Args:
            order: The Order being cancelled
        """
        # Release stock reservations
        from .stock_reservation_service import StockReservationService
        for item in order.items.all():
            try:
                StockReservationService.release_reservation(
                    item.stock_reservation,
                    reason="Order cancelled"
                )
            except Exception:
                # Reservation may not exist, skip
                pass


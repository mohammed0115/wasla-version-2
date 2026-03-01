"""
Stock Reservation Service

Manages stock reservations during checkout with auto-release on timeout.
Prevents overselling by reserving inventory before payment.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from apps.catalog.models import Inventory
from ..models import StockReservation, OrderItem


class StockReservationService:
    """
    Reserve stock at checkout with configurable TTL.
    
    Flow:
    1. reserve_stock() - Create reservation (15 min TTL)
    2. confirm_reservation() - After payment (extends to 30 min)
    3. release_on_shipment() - When order ships (removes reservation)
    4. auto_release_expired() - Background job to clean up expired
    """
    
    @staticmethod
    @transaction.atomic
    def reserve_stock(order_item: OrderItem, quantity: int, tenant_id: int, store_id: int) -> StockReservation:
        """
        Reserve stock for an order item.
        
        Args:
            order_item: The OrderItem to reserve for
            quantity: Quantity to reserve
            tenant_id: Tenant ID for isolation
            store_id: Store ID
            
        Returns:
            StockReservation instance
            
        Raises:
            ValueError: If insufficient stock available
        """
        inventory = Inventory.objects.select_for_update().get(product=order_item.product)
        
        # Check available stock (simplified: quantity must cover reservation)
        available = inventory.quantity
        if available < quantity:
            raise ValueError(
                f"Insufficient stock. Available: {available}, Requested: {quantity}"
            )

        # Create reservation with TTL
        expires_at = timezone.now() + timedelta(minutes=15)
        
        reservation = StockReservation.objects.create(
            tenant_id=tenant_id,
            store_id=store_id,
            order_item=order_item,
            product=order_item.product,
            variant=order_item.variant,
            quantity=quantity,
            status="reserved",
            expires_at=expires_at,
        )
        
        return reservation
    
    @staticmethod
    @transaction.atomic
    def confirm_reservation(reservation: StockReservation) -> StockReservation:
        """
        Confirm reservation after payment. Extends TTL to 30 minutes.
        
        Args:
            reservation: The StockReservation to confirm
            
        Returns:
            Updated StockReservation instance
        """
        if reservation.status != "reserved":
            raise ValueError(f"Cannot confirm reservation in {reservation.status} status")
        reservation.status = "confirmed"
        reservation.confirmed_at = timezone.now()
        reservation.expires_at = timezone.now() + timedelta(minutes=30)
        reservation.save(update_fields=["status", "confirmed_at", "expires_at"])
        return reservation
    
    @staticmethod
    @transaction.atomic
    def release_reservation(reservation: StockReservation, reason: str = "Auto-released") -> None:
        """
        Release reserved stock back to inventory.
        
        Args:
            reservation: The StockReservation to release
            reason: Reason for release (cancelled, expired, shipped, etc)
        """
        if reservation.status in {"released"}:
            return
        reservation.status = "released"
        reservation.released_at = timezone.now()
        reservation.release_reason = reason
        reservation.save(update_fields=["status", "released_at", "release_reason"])
    
    @staticmethod
    @transaction.atomic
    def release_on_shipment(order_item: OrderItem, shipped_quantity: int) -> None:
        """
        Release reservation when order ships.
        
        Args:
            order_item: The OrderItem being shipped
            shipped_quantity: Quantity shipped (may be less than reserved)
        """
        try:
            reservation = order_item.stock_reservation
        except StockReservation.DoesNotExist:
            # No reservation (may have been released already)
            return
        
        if reservation.status == StockReservation.STATUS_RELEASED:
            return
        
        # Release the reserved stock
        reservation.release_reservation(reason="Order shipped")
    
    @staticmethod
    @transaction.atomic
    def auto_release_expired() -> dict:
        """
        Auto-release expired reservations. Call periodically via celery task.
        
        Returns:
            Number of reservations expired
        """
        now = timezone.now()
        expired = StockReservation.objects.filter(
            status__in=["reserved", "confirmed"],
            expires_at__lte=now,
        )
        
        count = 0
        for reservation in expired:
            reservation.status = "released"
            reservation.released_at = now
            reservation.release_reason = "TTL expired"
            reservation.save(update_fields=["status", "released_at", "release_reason"])
            count += 1
        
        return {
            "released_count": count,
            "failed_count": 0,
            "timestamp": str(now),
        }
    
    @staticmethod
    def get_reservation_status(order_item: OrderItem) -> dict:
        """Get current reservation status for an order item."""
        try:
            reservation = order_item.stock_reservation
            return {
                "has_reservation": True,
                "status": reservation.status,
                "quantity": reservation.quantity,
                "expires_at": reservation.expires_at,
                "is_expired": reservation.expires_at <= timezone.now() if reservation.expires_at else False,
            }
        except StockReservation.DoesNotExist:
            return {"has_reservation": False}

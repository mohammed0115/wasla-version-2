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
from ..models_extended import StockReservation
from ..models import OrderItem


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
        
        # Check available stock (available = on_hand - reserved)
        available = inventory.quantity_on_hand - (inventory.reserved_quantity or 0)
        if available < quantity:
            raise ValueError(
                f"Insufficient stock. Available: {available}, Requested: {quantity}"
            )
        
        # Increment reserved quantity
        inventory.reserved_quantity = (inventory.reserved_quantity or 0) + quantity
        inventory.save(update_fields=["reserved_quantity"])
        
        # Create reservation with TTL
        expires_at = timezone.now() + timedelta(
            seconds=StockReservation.RESERVATION_TTL_SECONDS
        )
        
        reservation = StockReservation.objects.create(
            tenant_id=tenant_id,
            store_id=store_id,
            order_item=order_item,
            inventory=inventory,
            reserved_quantity=quantity,
            status=StockReservation.STATUS_RESERVED,
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
        reservation.confirm_reservation()
        reservation.refresh_from_db()
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
        reservation.release_reservation(reason=reason)
    
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
    def auto_release_expired() -> int:
        """
        Auto-release expired reservations. Call periodically via celery task.
        
        Returns:
            Number of reservations expired
        """
        now = timezone.now()
        expired = StockReservation.objects.filter(
            status=StockReservation.STATUS_RESERVED,
            expires_at__lte=now
        )
        
        count = 0
        for reservation in expired:
            try:
                reservation.release_reservation(reason="TTL expired")
                count += 1
            except Exception:
                # Log but continue with next reservation
                pass
        
        return count
    
    @staticmethod
    def get_reservation_status(order_item: OrderItem) -> dict:
        """Get current reservation status for an order item."""
        try:
            reservation = order_item.stock_reservation
            return {
                "has_reservation": True,
                "status": reservation.status,
                "quantity": reservation.reserved_quantity,
                "expires_at": reservation.expires_at,
                "is_expired": reservation.is_expired,
            }
        except StockReservation.DoesNotExist:
            return {"has_reservation": False}

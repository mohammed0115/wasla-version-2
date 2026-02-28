"""
Stock Management Service - Prevents overselling via reservations.

Workflow:
1. reserve() - Called at checkout, holds stock for 30 mins
2. confirm() - Called when payment succeeds, extends hold until shipment
3. release() - Called on timeout/cancellation, frees stock
"""

from __future__ import annotations

from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import logging

from apps.orders.models import StockReservation, OrderItem
from apps.catalog.models import Product, ProductVariant

logger = logging.getLogger("orders.stock")


class StockManagementService:
    RESERVATION_TIMEOUT_MINUTES = 30
    
    @staticmethod
    @transaction.atomic
    def reserve_order_items(order_item: OrderItem, timeout_minutes: int = 30) -> StockReservation:
        """
        Reserve stock for an order item.
        
        Args:
            order_item: OrderItem to reserve
            timeout_minutes: Default 30 minutes
            
        Returns:
            StockReservation instance
            
        Raises:
            ValueError: If not enough stock available
        """
        product = order_item.product
        variant = order_item.variant
        quantity = order_item.quantity
        
        # Check available stock
        available = StockManagementService._get_available_stock(product, variant)
        if available < quantity:
            logger.warning(
                "Insufficient stock for reservation",
                extra={
                    "product_id": product.id,
                    "variant_id": variant.id if variant else None,
                    "requested": quantity,
                    "available": available,
                },
            )
            raise ValueError(f"Insufficient stock: only {available} available, {quantity} requested")
        
        expires_at = timezone.now() + timedelta(minutes=timeout_minutes)
        
        reservation, created = StockReservation.objects.get_or_create(
            order_item=order_item,
            defaults={
                "tenant_id": order_item.tenant_id,
                "product": product,
                "variant": variant,
                "quantity": quantity,
                "status": StockReservation.STATUS_CHOICES[0][0],  # "reserved"
                "expires_at": expires_at,
            },
        )
        
        if created:
            logger.info(
                "Stock reserved",
                extra={
                    "product_id": product.id,
                    "quantity": quantity,
                    "expires_at": expires_at.isoformat(),
                },
            )
        
        return reservation
    
    @staticmethod
    @transaction.atomic
    def confirm_reservation(reservation: StockReservation) -> StockReservation:
        """
        Confirm reservation (payment succeeded).
        Extends hold until shipment completes.
        """
        reservation.status = "confirmed"
        reservation.confirmed_at = timezone.now()
        reservation.expires_at = timezone.now() + timedelta(days=30)  # Hold for 30 days
        reservation.save(update_fields=["status", "confirmed_at", "expires_at"])
        
        logger.info(
            "Stock reservation confirmed",
            extra={
                "reservation_id": str(reservation.id),
                "product_id": reservation.product.id,
                "quantity": reservation.quantity,
            },
        )
        
        return reservation
    
    @staticmethod
    @transaction.atomic
    def release_reservation(reservation: StockReservation, reason: str = "manual") -> StockReservation:
        """
        Release/cancel a reservation.
        Called on order cancellation, timeout, or return completion.
        """
        reservation.status = "released"
        reservation.released_at = timezone.now()
        reservation.save(update_fields=["status", "released_at"])
        
        logger.info(
            "Stock reservation released",
            extra={
                "reservation_id": str(reservation.id),
                "product_id": reservation.product.id,
                "reason": reason,
            },
        )
        
        return reservation
    
    @staticmethod
    def auto_release_expired_reservations() -> int:
        """
        Celery task: Release reservations past timeout.
        Run every 5 minutes.
        """
        expired = StockReservation.objects.filter(
            status="reserved",
            expires_at__lt=timezone.now(),
        )
        
        count = 0
        for reservation in expired:
            StockManagementService.release_reservation(reservation, reason="timeout")
            count += 1
        
        logger.info(f"Released {count} expired stock reservations")
        return count
    
    @staticmethod
    def _get_available_stock(product: Product, variant: ProductVariant | None = None) -> int:
        """
        Calculate available stock (total - reserved - sold).
        For MVP, this is a simplified check.
        """
        if variant:
            # Use variant stock if available
            return max(0, variant.stock - StockManagementService._count_reserved(product, variant))
        else:
            # Use product stock
            return max(0, product.stock - StockManagementService._count_reserved(product, None))
    
    @staticmethod
    def _count_reserved(product: Product, variant: ProductVariant | None = None) -> int:
        """Count active reservations for a product/variant."""
        from django.db.models import Sum
        
        query = StockReservation.objects.filter(
            product=product,
            status__in=["reserved", "confirmed"],
        )
        if variant:
            query = query.filter(variant=variant)
        
        result = query.aggregate(total=Sum('quantity'))
        return result['total'] or 0

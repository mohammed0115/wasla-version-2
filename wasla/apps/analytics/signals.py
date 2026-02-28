"""
Analytics event tracking signals.

Automatically tracks events:
- product_view: When a product is viewed on storefront
- add_to_cart: When item added to cart
- checkout_started: When checkout flow begins
- purchase_completed: When order is completed
"""

from __future__ import annotations

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from decimal import Decimal

from apps.orders.models import Order
from apps.cart.models import CartItem
from apps.analytics.application.dashboard_services import EventTrackingService


# ============================================================================
# Order Signals - Track Purchase Completion
# ============================================================================

@receiver(post_save, sender=Order)
def track_order_completion(sender, instance: Order, created: bool, **kwargs):
    """
    Track purchase_completed event when order status changes to completed/paid.
    """
    # Only track on status change to completed/paid
    if instance.status in [Order.STATUS_COMPLETED, Order.STATUS_PAID]:
        # Calculate order value from items
        order_value = instance.total_amount or Decimal('0.00')
        item_count = instance.items.count()

        # Track event
        EventTrackingService.track_purchase_completed(
            store_id=instance.store_id,
            order_id=instance.id,
            user_id=instance.customer_id,
            session_key=None,  # Can be retrieved from request context
            order_value=order_value,
            item_count=item_count
        )


# ============================================================================
# Cart Item Signals - Track Add to Cart
# ============================================================================

@receiver(post_save, sender=CartItem)
def track_add_to_cart(sender, instance: CartItem, created: bool, **kwargs):
    """
    Track add_to_cart event when item is added to cart.
    """
    if created:
        from apps.catalog.models import ProductVariant

        try:
            variant = ProductVariant.objects.get(id=instance.variant_id)
            product_id = variant.product_id

            EventTrackingService.track_add_to_cart(
                store_id=instance.cart.store_id,
                product_id=product_id,
                variant_id=instance.variant_id,
                quantity=instance.quantity,
                user_id=instance.cart.customer_id,
                session_key=None,
            )
        except:
            # Silently fail if product/variant not found
            pass


# ============================================================================
# Checkout Start Signal
# ============================================================================

def track_checkout_started(store_id: int, cart: object, user_id: int | None = None,
                          session_key: str | None = None):
    """
    Call this function when checkout flow is initiated.

    Should be called from checkout views when user starts checkout.
    """
    item_count = cart.items.count()
    cart_value = cart.get_total() if hasattr(cart, 'get_total') else None

    EventTrackingService.track_checkout_started(
        store_id=store_id,
        cart_id=cart.id,
        user_id=user_id,
        session_key=session_key,
        item_count=item_count,
        cart_value=cart_value,
    )


# ============================================================================
# Product View Tracking
# ============================================================================

def track_product_view(store_id: int, product_id: int, user_id: int | None = None,
                      session_key: str | None = None):
    """
    Call this function when a product is viewed on the storefront.

    Should be called from product detail view.
    """
    EventTrackingService.track_product_view(
        store_id=store_id,
        product_id=product_id,
        user_id=user_id,
        session_key=session_key,
    )

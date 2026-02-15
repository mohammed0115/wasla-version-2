from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

from cart.models import Cart, CartItem
from analytics.models import Event
from catalog.models import Product
from orders.models import OrderItem, Order


def recommend_for_product(*, tenant_id: int, product_id: int, limit: int = 8) -> list[int]:
    product = Product.objects.filter(store_id=tenant_id, id=product_id).first()
    if not product:
        return []

    categories = list(product.categories.values_list("id", flat=True))
    qs = Product.objects.filter(store_id=tenant_id, is_active=True).exclude(id=product.id)
    if categories:
        qs = qs.filter(categories__in=categories)

    if product.price:
        lower = product.price * Decimal("0.8")
        upper = product.price * Decimal("1.2")
        qs = qs.filter(price__gte=lower, price__lte=upper)

    return list(qs.distinct().values_list("id", flat=True)[:limit])


def recommend_for_cart(*, tenant_id: int, cart_id: int, limit: int = 8) -> list[int]:
    cart = Cart.objects.filter(store_id=tenant_id, id=cart_id).first()
    if not cart:
        return []

    cart_items = list(CartItem.objects.filter(cart=cart).values_list("product_id", flat=True))
    if not cart_items:
        return []

    categories = (
        Product.objects.filter(store_id=tenant_id, id__in=cart_items)
        .values_list("categories__id", flat=True)
    )
    qs = Product.objects.filter(store_id=tenant_id, is_active=True).exclude(id__in=cart_items)
    qs = qs.filter(categories__id__in=list(categories))
    return list(qs.distinct().values_list("id", flat=True)[:limit])


def recommend_for_home(*, tenant_id: int, limit: int = 8) -> list[int]:
    top_sellers = (
        OrderItem.objects.filter(order__store_id=tenant_id, order__payment_status="paid")
        .values("product_id")
        .annotate(total_qty=Sum("quantity"))
        .order_by("-total_qty")
    )
    ids = [row["product_id"] for row in top_sellers[:limit]]
    if ids:
        return ids

    recent_view_ids = (
        Event.objects.filter(
            tenant_id=tenant_id,
            event_name="product.viewed",
            object_type="PRODUCT",
        )
        .exclude(object_id="")
        .order_by("-occurred_at")
        .values_list("object_id", flat=True)[:100]
    )
    seen: set[int] = set()
    ordered_ids: list[int] = []
    for raw_id in recent_view_ids:
        try:
            product_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if product_id in seen:
            continue
        seen.add(product_id)
        ordered_ids.append(product_id)
        if len(ordered_ids) >= limit:
            break

    if ordered_ids:
        active_ids = set(
            Product.objects.filter(store_id=tenant_id, is_active=True, id__in=ordered_ids)
            .values_list("id", flat=True)
        )
        return [pid for pid in ordered_ids if pid in active_ids][:limit]

    recent = (
        Order.objects.filter(store_id=tenant_id)
        .order_by("-created_at")
        .values_list("id", flat=True)[:10]
    )
    product_ids = (
        OrderItem.objects.filter(order_id__in=list(recent))
        .values_list("product_id", flat=True)[:limit]
    )
    return list(product_ids)

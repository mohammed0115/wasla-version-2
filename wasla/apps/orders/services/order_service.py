import uuid
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.catalog.models import Inventory
from apps.subscriptions.services.entitlement_service import SubscriptionEntitlementService

from ..models import Order, OrderItem
from .pricing_service import PricingService


class OrderService:
    @staticmethod
    @transaction.atomic
    def create_order(customer, items, store_id: int | None = None):
        resolved_store_id = store_id if store_id is not None else getattr(customer, "store_id", 1)
        customer_store_id = getattr(customer, "store_id", resolved_store_id)
        if customer_store_id != resolved_store_id:
            raise ValueError("Customer store does not match order store")

        for item in items or []:
            product = item.get("product")
            product_store_id = getattr(product, "store_id", resolved_store_id)
            if product_store_id != resolved_store_id:
                raise ValueError("Product store does not match order store")

        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_start.month == 12:
            next_month_start = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month_start = month_start.replace(month=month_start.month + 1)

        current_orders = Order.objects.filter(
            store_id=resolved_store_id,
            created_at__gte=month_start,
            created_at__lt=next_month_start,
        ).count()
        SubscriptionEntitlementService.assert_within_limit(
            store_id=resolved_store_id,
            limit_field="max_orders_monthly",
            current_usage=current_orders,
            increment=1,
        )

        total = PricingService.calculate_total(items)
        order = Order.objects.create(
            store_id=resolved_store_id,
            order_number=str(uuid.uuid4())[:12],
            customer=customer,
            status="pending",
            total_amount=total
        )
        for item in items:
            OrderItem.objects.create(
                order=order,
                product=item["product"],
                quantity=item["quantity"],
                price=item["price"]
            )
        return order

    @staticmethod
    def validate_stock(order) -> None:
        items = list(order.items.select_related("product"))
        if not items:
            raise ValueError("Order has no items")

        inventory_map = {
            inv.product_id: inv
            for inv in Inventory.objects.filter(product_id__in=[item.product_id for item in items])
        }
        for item in items:
            inventory = inventory_map.get(item.product_id)
            if not inventory:
                raise ValueError(f"No inventory for product '{item.product}'")
            if inventory.quantity < item.quantity:
                raise ValueError(
                    f"Insufficient stock for '{item.product}' (available {inventory.quantity})"
                )

    @staticmethod
    @transaction.atomic
    def mark_as_paid(order) -> None:
        if order.status != "pending":
            raise ValueError("Order must be pending to mark as paid")

        OrderService.validate_stock(order)

        items = list(order.items.select_related("product"))
        for item in items:
            updated = Inventory.objects.filter(
                product_id=item.product_id,
                quantity__gte=item.quantity,
            ).update(quantity=F("quantity") - item.quantity)
            if updated == 0:
                raise ValueError(f"Insufficient stock for '{item.product}'")

        for inventory in Inventory.objects.filter(product_id__in=[i.product_id for i in items]).select_related(
            "product"
        ):
            quantity = inventory.quantity
            in_stock = quantity > 0
            if inventory.in_stock != in_stock:
                inventory.in_stock = in_stock
                inventory.save(update_fields=["in_stock"])

            if inventory.product.is_active != in_stock:
                inventory.product.is_active = in_stock
                inventory.product.save(update_fields=["is_active"])

        order.status = "paid"
        if hasattr(order, "payment_status"):
            order.payment_status = "paid"
            order.save(update_fields=["status", "payment_status"])
        else:
            order.save(update_fields=["status"])

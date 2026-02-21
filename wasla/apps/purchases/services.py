from django.db import transaction
from django.db.models import F

from apps.catalog.models import Inventory, StockMovement
from apps.purchases.models import GoodsReceiptNote, PurchaseOrder


class PurchaseReceivingService:
    """Receive a purchase order and increase stock."""

    @staticmethod
    @transaction.atomic
    def receive_purchase_order(purchase_order: PurchaseOrder, note: str = "") -> GoodsReceiptNote:
        if purchase_order.status == PurchaseOrder.STATUS_RECEIVED:
            # Idempotent-ish: create another GRN? we keep simple and block.
            raise ValueError("Purchase order already received")

        if purchase_order.status == PurchaseOrder.STATUS_CANCELLED:
            raise ValueError("Cannot receive a cancelled purchase order")

        items = list(purchase_order.items.select_related("product"))
        if not items:
            raise ValueError("Purchase order has no items")

        # Increase stock
        for item in items:
            Inventory.objects.update_or_create(
                product=item.product,
                defaults={"in_stock": True},
            )
            Inventory.objects.filter(product=item.product).update(quantity=F("quantity") + item.quantity)

            StockMovement.objects.create(
                store_id=purchase_order.store_id,
                product=item.product,
                movement_type=StockMovement.TYPE_IN,
                quantity=item.quantity,
                reason="purchase_received",
                purchase_order_id=purchase_order.id,
            )

        purchase_order.status = PurchaseOrder.STATUS_RECEIVED
        purchase_order.save(update_fields=["status"])

        return GoodsReceiptNote.objects.create(purchase_order=purchase_order, note=note)

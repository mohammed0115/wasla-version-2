from django.db import models


class Supplier(models.Model):
    """Supplier master data (per store)."""

    store_id = models.IntegerField(default=1, db_index=True)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    address = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["store_id", "name"])]

    def __str__(self) -> str:
        return self.name


class PurchaseOrder(models.Model):
    """Purchase Order header."""

    STATUS_DRAFT = "DRAFT"
    STATUS_SENT = "SENT"
    STATUS_RECEIVED = "RECEIVED"
    STATUS_CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SENT, "Sent"),
        (STATUS_RECEIVED, "Received"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    store_id = models.IntegerField(default=1, db_index=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    reference = models.CharField(max_length=50, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["store_id", "created_at"])]

    def __str__(self) -> str:
        return f"PO#{self.id} ({self.status})"


class PurchaseOrderItem(models.Model):
    """Purchase Order line items."""

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        indexes = [models.Index(fields=["purchase_order", "product"])]

    def __str__(self) -> str:
        return f"{self.product_id} x {self.quantity}"


class GoodsReceiptNote(models.Model):
    """GRN — records receiving against a purchase order."""

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="receipts")
    received_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return f"GRN#{self.id} for PO#{self.purchase_order_id}"

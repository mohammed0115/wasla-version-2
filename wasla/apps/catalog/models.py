"""
Catalog models (MVP).

AR:
- هذا الملف يحتوي موديلات الكتالوج: التصنيفات، المنتجات، والمخزون.
- عزل المتاجر يتم عبر `store_id` (Tenant column).

EN:
- Contains catalog models: categories, products, and inventory.
- Tenant isolation is implemented via `store_id`.
"""

from django.db import models


class Category(models.Model):
    """Store-scoped product category."""

    store_id = models.IntegerField(default=1, db_index=True)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self) -> str:
        return self.name


def product_image_upload_to(instance, filename: str) -> str:
    """Upload path for product images (scoped by store)."""

    return f"store_{instance.store_id}/products/{filename}"


class Product(models.Model):
    """Sellable product within a store (unique SKU per store)."""

    store_id = models.IntegerField(default=1, db_index=True)
    sku = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    description_ar = models.TextField(blank=True, default="")
    description_en = models.TextField(blank=True, default="")
    image = models.ImageField(upload_to=product_image_upload_to, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    categories = models.ManyToManyField(Category, related_name="products", blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["store_id", "sku"], name="uq_product_store_sku"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"


class Inventory(models.Model):
    """Basic inventory record for a product."""

    product = models.OneToOneField(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    in_stock = models.BooleanField(default=True)
    # Alert threshold used in merchant dashboard.
    low_stock_threshold = models.PositiveIntegerField(default=5)

    def __str__(self) -> str:
        return f"{self.product} - qty={self.quantity}"


class StockMovement(models.Model):
    """Lightweight stock ledger (Phase 3).

    Notes:
    - store_id for tenancy isolation (same as Product.store_id)
    - quantity is always positive; direction via movement_type
    """

    TYPE_IN = "IN"
    TYPE_OUT = "OUT"
    TYPE_ADJUST = "ADJUST"
    TYPE_CHOICES = [
        (TYPE_IN, "In"),
        (TYPE_OUT, "Out"),
        (TYPE_ADJUST, "Adjustment"),
    ]

    store_id = models.IntegerField(default=1, db_index=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_movements")
    movement_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    quantity = models.PositiveIntegerField()
    reason = models.CharField(max_length=255, blank=True, default="")

    # Optional references (keep as ints to avoid circular imports)
    order_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    purchase_order_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "created_at"]),
            models.Index(fields=["store_id", "product"]),
        ]

    def __str__(self) -> str:
        return f"store={self.store_id} product={self.product_id} {self.movement_type} {self.quantity}"

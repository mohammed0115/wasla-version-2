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

    def __str__(self) -> str:
        return f"{self.product} - qty={self.quantity}"

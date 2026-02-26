"""
Catalog models (MVP).

AR:
- هذا الملف يحتوي موديلات الكتالوج: التصنيفات، المنتجات، والمخزون.
- عزل المتاجر يتم عبر `store_id` (Tenant column).

EN:
- Contains catalog models: categories, products, and inventory.
- Tenant isolation is implemented via `store_id`.
"""

import os
from io import BytesIO

from django.core.files.base import ContentFile
from django.db import models, transaction
from django.db.models import Q


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


def product_gallery_upload_to(instance, filename: str) -> str:
    """Upload path for product gallery images."""

    return f"store_{instance.product.store_id}/products/gallery/{filename}"


def optimize_image_file(image_field):
    """Best-effort image optimization for uploaded product images."""

    if not image_field:
        return image_field

    try:
        from PIL import Image, ImageOps
    except Exception:
        return image_field

    try:
        image_field.file.seek(0)
        image = Image.open(image_field.file)
        image = ImageOps.exif_transpose(image)
        image.thumbnail((1600, 1600))

        image_format = (image.format or "JPEG").upper()
        output = BytesIO()
        save_kwargs = {}
        extension = ".jpg"

        if image_format in {"JPEG", "JPG"}:
            if image.mode in {"RGBA", "P"}:
                image = image.convert("RGB")
            image_format = "JPEG"
            extension = ".jpg"
            save_kwargs = {"quality": 85, "optimize": True}
        elif image_format == "PNG":
            extension = ".png"
            save_kwargs = {"optimize": True, "compress_level": 7}
        elif image_format == "WEBP":
            extension = ".webp"
            save_kwargs = {"quality": 85, "method": 6}
        else:
            if image.mode in {"RGBA", "P"}:
                image = image.convert("RGB")
            image_format = "JPEG"
            extension = ".jpg"
            save_kwargs = {"quality": 85, "optimize": True}

        image.save(output, format=image_format, **save_kwargs)
        output.seek(0)

        base_name, _ = os.path.splitext(image_field.name)
        optimized_name = f"{base_name}{extension}"
        return ContentFile(output.read(), name=optimized_name)
    except Exception:
        return image_field


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


class ProductOptionGroup(models.Model):
    """Store-scoped product option group (e.g. Color, Size)."""

    store = models.ForeignKey("stores.Store", on_delete=models.CASCADE, related_name="product_option_groups")
    name = models.CharField(max_length=120)
    is_required = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["store", "name"], name="uq_product_option_group_store_name"),
        ]
        indexes = [
            models.Index(fields=["store", "position"]),
        ]

    def __str__(self) -> str:
        return f"{self.store_id}:{self.name}"


class ProductOption(models.Model):
    """Option value inside a group (e.g. Red under Color)."""

    group = models.ForeignKey(ProductOptionGroup, on_delete=models.CASCADE, related_name="options")
    value = models.CharField(max_length=120)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["group", "value"], name="uq_product_option_group_value"),
        ]

    def __str__(self) -> str:
        return f"{self.group_id}:{self.value}"


class ProductVariant(models.Model):
    """Sellable variant for a product scoped by store SKU uniqueness."""

    store_id = models.IntegerField(default=1, db_index=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=64)
    price_override = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    options = models.ManyToManyField(ProductOption, related_name="variants", blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["store_id", "sku"], name="uq_product_variant_store_sku"),
        ]
        indexes = [
            models.Index(fields=["product", "is_active"]),
            models.Index(fields=["store_id", "product"]),
        ]

    def save(self, *args, **kwargs):
        if self.product_id:
            self.store_id = self.product.store_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.product_id}:{self.sku}"


class ProductImage(models.Model):
    """Multiple images per product with a single primary image."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=product_gallery_upload_to)
    alt_text = models.CharField(max_length=255, blank=True, default="")
    position = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product"],
                condition=Q(is_primary=True),
                name="uq_productimage_single_primary",
            )
        ]
        indexes = [
            models.Index(fields=["product", "position"]),
        ]
        ordering = ["position", "id"]

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if self.image:
            self.image = optimize_image_file(self.image)

        with transaction.atomic():
            if self.is_primary:
                ProductImage.objects.filter(product_id=self.product_id, is_primary=True).exclude(pk=self.pk).update(
                    is_primary=False
                )

            super().save(*args, **kwargs)

            product_images = ProductImage.objects.filter(product_id=self.product_id)
            has_primary = product_images.filter(is_primary=True).exists()

            if is_new and not product_images.exclude(pk=self.pk).exists():
                ProductImage.objects.filter(pk=self.pk).update(is_primary=True)
                self.is_primary = True
                has_primary = True

            if self.is_primary:
                has_primary = True

            if not has_primary:
                ProductImage.objects.filter(pk=self.pk).update(is_primary=True)
                self.is_primary = True

            if self.is_primary:
                Product.objects.filter(pk=self.product_id).update(image=self.image.name)

    def delete(self, *args, **kwargs):
        product_id = self.product_id
        was_primary = self.is_primary
        super().delete(*args, **kwargs)

        if not was_primary:
            return

        replacement = ProductImage.objects.filter(product_id=product_id).order_by("position", "id").first()
        if replacement:
            ProductImage.objects.filter(pk=replacement.pk).update(is_primary=True)
            Product.objects.filter(pk=product_id).update(image=replacement.image.name)
        else:
            Product.objects.filter(pk=product_id).update(image="")

    def __str__(self) -> str:
        return f"product={self.product_id} primary={self.is_primary}"


class Inventory(models.Model):
    """Basic inventory record for a product."""

    product = models.OneToOneField(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    in_stock = models.BooleanField(default=True)
    # Alert threshold used in merchant dashboard.
    low_stock_threshold = models.PositiveIntegerField(default=5)

    def save(self, *args, **kwargs):
        quantity = max(0, int(self.quantity or 0))
        in_stock = quantity > 0
        self.quantity = quantity
        self.in_stock = in_stock

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            normalized = set(update_fields)
            normalized.update({"quantity", "in_stock"})
            kwargs["update_fields"] = list(normalized)

        super().save(*args, **kwargs)
        Product.objects.filter(pk=self.product_id).exclude(is_active=in_stock).update(is_active=in_stock)

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
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )
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

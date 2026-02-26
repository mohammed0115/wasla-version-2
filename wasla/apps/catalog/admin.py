from django.contrib import admin

from apps.catalog.models import (
    Category,
    Inventory,
    Product,
    ProductImage,
    ProductOption,
    ProductOptionGroup,
    ProductVariant,
    StockMovement,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "name", "price", "is_active")
    list_filter = ("store_id", "is_active")
    search_fields = ("name",)


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "quantity", "low_stock_threshold", "in_stock")
    list_filter = ("in_stock",)
    search_fields = ("product__name",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "product", "variant", "movement_type", "quantity", "created_at")
    list_filter = ("store_id", "movement_type")
    search_fields = ("product__name", "reason")


@admin.register(ProductOptionGroup)
class ProductOptionGroupAdmin(admin.ModelAdmin):
    list_display = ("id", "store", "name", "is_required", "position")
    list_filter = ("store", "is_required")
    search_fields = ("name",)


@admin.register(ProductOption)
class ProductOptionAdmin(admin.ModelAdmin):
    list_display = ("id", "group", "value")
    search_fields = ("value", "group__name")


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "product", "sku", "price_override", "stock_quantity", "is_active")
    list_filter = ("store_id", "is_active")
    search_fields = ("sku", "product__name")


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "position", "is_primary")
    list_filter = ("is_primary",)
    search_fields = ("product__name", "alt_text")

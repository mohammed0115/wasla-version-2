from django.contrib import admin

from apps.catalog.models import Category, Inventory, Product, StockMovement


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
    list_display = ("id", "store_id", "product", "movement_type", "quantity", "created_at")
    list_filter = ("store_id", "movement_type")
    search_fields = ("product__name", "reason")

from django.contrib import admin

from apps.purchases.models import GoodsReceiptNote, PurchaseOrder, PurchaseOrderItem, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "name", "phone", "email", "created_at")
    search_fields = ("name", "phone", "email")
    list_filter = ("store_id",)


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "supplier", "status", "created_at")
    list_filter = ("store_id", "status")
    search_fields = ("id", "reference", "supplier__name")
    inlines = [PurchaseOrderItemInline]


@admin.register(GoodsReceiptNote)
class GoodsReceiptNoteAdmin(admin.ModelAdmin):
    list_display = ("id", "purchase_order", "received_at")
    search_fields = ("purchase_order__id",)

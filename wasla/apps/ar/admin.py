from django.contrib import admin

from apps.ar.models import ARSession, ProductARAsset


@admin.register(ProductARAsset)
class ProductARAssetAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "product", "is_active", "created_at")
    list_filter = ("is_active", "store_id")
    search_fields = ("product__name", "product__sku")


@admin.register(ARSession)
class ARSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "tenant_id", "product", "user", "started_at", "ended_at")
    list_filter = ("store_id", "tenant_id")
    search_fields = ("product__name", "user__username", "session_id")

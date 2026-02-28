"""Django admin configuration for storefront."""
from django.contrib import admin
from .models import ProductSEO, CategorySEO, ProductSearch, StorefrontSettings


@admin.register(ProductSEO)
class ProductSEOAdmin(admin.ModelAdmin):
    list_display = ("product", "slug", "meta_title", "updated_at")
    search_fields = ("product__name", "slug", "meta_title")
    list_filter = ("created_at", "updated_at")
    prepopulated_fields = {"slug": ("product__name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(CategorySEO)
class CategorySEOAdmin(admin.ModelAdmin):
    list_display = ("category", "slug", "meta_title", "updated_at")
    search_fields = ("category__name", "slug", "meta_title")
    list_filter = ("created_at", "updated_at")
    prepopulated_fields = {"slug": ("category__name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProductSearch)
class ProductSearchAdmin(admin.ModelAdmin):
    list_display = ("product", "updated_at")
    search_fields = ("product__name", "search_text")
    list_filter = ("created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")


@admin.register(StorefrontSettings)
class StorefrontSettingsAdmin(admin.ModelAdmin):
    list_display = ("store", "product_per_page", "enable_search", "enable_filters", "updated_at")
    search_fields = ("store__name",)
    list_filter = ("enable_search", "enable_filters", "enable_wishlist", "enable_reviews")
    readonly_fields = ("created_at", "updated_at")

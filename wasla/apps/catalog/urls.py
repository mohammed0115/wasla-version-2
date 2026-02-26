from django.urls import path

from apps.catalog.api import (
    LowStockAPI,
    ProductUpsertAPI,
    ProductUpdateAPI,
    StockMovementsAPI,
    VariantPriceResolveAPI,
    VariantStockAPI,
)
from apps.catalog import views

app_name = "catalog"

# API endpoints
api_patterns = [
    path("catalog/products/", ProductUpsertAPI.as_view()),
    path("catalog/products/<int:product_id>/", ProductUpdateAPI.as_view()),
    path("catalog/products/<int:product_id>/price/", VariantPriceResolveAPI.as_view()),
    path("catalog/variants/<int:variant_id>/stock/", VariantStockAPI.as_view()),
    path("merchants/inventory/low-stock/", LowStockAPI.as_view()),
    path("merchants/inventory/movements/", StockMovementsAPI.as_view()),
]

# Dashboard web views
dashboard_patterns = [
    path("dashboard/products/", views.product_list, name="product_list"),
    path("dashboard/products/create/", views.product_create, name="product_create"),
    path("dashboard/products/<int:product_id>/", views.product_detail, name="product_detail"),
    path("dashboard/products/<int:product_id>/edit/", views.product_edit, name="product_edit"),
    # Option groups
    path("dashboard/products/<int:product_id>/option-groups/create/", views.option_group_create, name="option_group_create"),
    path("dashboard/products/<int:product_id>/option-groups/<int:group_id>/edit/", views.option_group_edit, name="option_group_edit"),
    # Variants
    path("dashboard/products/<int:product_id>/variants/create/", views.variant_create, name="variant_create"),
    path("dashboard/products/<int:product_id>/variants/<int:variant_id>/edit/", views.variant_edit, name="variant_edit"),
    path("dashboard/products/<int:product_id>/variants/<int:variant_id>/delete/", views.variant_delete, name="variant_delete"),
    # Variant stock API
    path("dashboard/variants/<int:variant_id>/stock/", views.variant_stock_api, name="variant_stock_api"),
]

urlpatterns = api_patterns + dashboard_patterns

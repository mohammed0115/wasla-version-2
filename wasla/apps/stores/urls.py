from django.urls import path

from .merchant_views import (
    merchant_category_create,
    merchant_category_delete,
    merchant_category_edit,
    merchant_category_list,
    merchant_order_change_status,
    merchant_order_detail,
    merchant_order_refund_placeholder,
    merchant_orders_list,
    merchant_product_create,
    merchant_product_delete,
    merchant_product_edit,
    merchant_product_list,
)
from .views import (
    merchant_register,
    store_setup_basic,
    store_setup_products,
    store_setup_design,
    store_setup_domain,
    store_setup_success,
    store_dashboard,
)


app_name = "stores"


urlpatterns = [
    path("merchant/register", merchant_register, name="merchant_register"),
    path("merchant/setup/basic", store_setup_basic, name="store_setup_basic"),
    path("merchant/setup/products", store_setup_products, name="store_setup_products"),
    path("merchant/setup/design", store_setup_design, name="store_setup_design"),
    path("merchant/setup/domain", store_setup_domain, name="store_setup_domain"),
    path("merchant/setup/success", store_setup_success, name="store_setup_success"),
    path("merchant/dashboard", store_dashboard, name="store_dashboard"),
    path("merchant/dashboard/<int:store_id>", store_dashboard, name="store_dashboard_with_id"),

    # Phase 1 — Merchant Core
    path("merchant/dashboard/products", merchant_product_list, name="merchant_products"),
    path("merchant/dashboard/products/create", merchant_product_create, name="merchant_product_create"),
    path("merchant/dashboard/products/<int:product_id>/edit", merchant_product_edit, name="merchant_product_edit"),
    path("merchant/dashboard/products/<int:product_id>/delete", merchant_product_delete, name="merchant_product_delete"),

    path("merchant/dashboard/categories", merchant_category_list, name="merchant_categories"),
    path("merchant/dashboard/categories/create", merchant_category_create, name="merchant_category_create"),
    path("merchant/dashboard/categories/<int:category_id>/edit", merchant_category_edit, name="merchant_category_edit"),
    path("merchant/dashboard/categories/<int:category_id>/delete", merchant_category_delete, name="merchant_category_delete"),

    path("merchant/dashboard/orders", merchant_orders_list, name="merchant_orders"),
    path("merchant/dashboard/orders/<uuid:order_id>", merchant_order_detail, name="merchant_order_detail"),
    path("merchant/dashboard/orders/<uuid:order_id>/status", merchant_order_change_status, name="merchant_order_change_status"),
    path("merchant/dashboard/orders/<uuid:order_id>/refund", merchant_order_refund_placeholder, name="merchant_order_refund"),
]

"""Storefront URL routing."""
from django.urls import path
from . import views

app_name = "storefront"

urlpatterns = [
    # Storefront pages
    path("store/", views.storefront_home, name="home"),
    path("store/products/", views.product_list, name="product_list"),
    path("store/category/<slug:slug>/", views.category_products, name="category"),
    path("store/search/", views.product_search, name="search"),
    path("store/product/<slug:slug>/", views.product_detail_sf, name="product_detail"),

    # Customer account
    path("customer/orders/", views.customer_orders, name="customer_orders"),
    path("customer/addresses/", views.customer_addresses, name="customer_addresses"),
    path("customer/reorder/<int:order_id>/", views.customer_reorder, name="customer_reorder"),
]

from django.urls import path

from . import views


app_name = "cart"

urlpatterns = [
    path("cart/", views.cart_view, name="cart_view"),
    path("store/cart", views.cart_view, name="store_cart_view"),
    path("store/cart/", views.cart_view, name="store_cart_view_slash"),
    path("cart/add", views.cart_add, name="cart_add"),
    path("cart/update", views.cart_update, name="cart_update"),
    path("cart/remove", views.cart_remove, name="cart_remove"),
    path("store/<slug:store_slug>/products/<int:product_id>/", views.product_detail, name="product_detail"),
]

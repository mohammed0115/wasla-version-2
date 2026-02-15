from django.urls import path

from . import views


app_name = "checkout"

urlpatterns = [
    path("checkout/address", views.checkout_address, name="checkout_address"),
    path("checkout/shipping", views.checkout_shipping, name="checkout_shipping"),
    path("checkout/payment", views.checkout_payment, name="checkout_payment"),
    path("order/confirmation/<str:order_number>", views.order_confirmation, name="order_confirmation"),
]

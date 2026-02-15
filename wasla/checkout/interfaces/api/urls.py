from django.urls import path

from .views import CheckoutAddressAPI, CheckoutOrderAPI, CheckoutShippingAPI, CheckoutStartAPI


urlpatterns = [
    path("checkout/start", CheckoutStartAPI.as_view()),
    path("checkout/address", CheckoutAddressAPI.as_view()),
    path("checkout/shipping", CheckoutShippingAPI.as_view()),
    path("checkout/order", CheckoutOrderAPI.as_view()),
]

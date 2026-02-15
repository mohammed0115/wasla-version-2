from django.urls import path

from .views import CartAddAPI, CartDetailAPI, CartRemoveAPI, CartUpdateAPI


urlpatterns = [
    path("cart", CartDetailAPI.as_view()),
    path("cart/add", CartAddAPI.as_view()),
    path("cart/update", CartUpdateAPI.as_view()),
    path("cart/remove", CartRemoveAPI.as_view()),
]

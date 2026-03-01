from django.urls import path

from .views import (
    CartAddAPI,
    CartApplyCouponAPI,
    CartDetailAPI,
    CartRemoveAPI,
    CartRemoveCouponAPI,
    CartUpdateAPI,
)


urlpatterns = [
    path("cart", CartDetailAPI.as_view()),
    path("cart/add", CartAddAPI.as_view()),
    path("cart/update", CartUpdateAPI.as_view()),
    path("cart/remove", CartRemoveAPI.as_view()),
    path("cart/coupon/apply", CartApplyCouponAPI.as_view()),
    path("cart/coupon/remove", CartRemoveCouponAPI.as_view()),
]

"""Coupon URLs."""
from django.urls import path
from apps.coupons import views

app_name = "coupons"

urlpatterns = [
    path("api/coupons/validate/", views.validate_coupon, name="validate"),
    path("api/coupons/<str:code>/", views.get_coupon_details, name="details"),
]

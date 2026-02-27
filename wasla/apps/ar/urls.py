from django.urls import path

from apps.ar.api import ProductARDataAPI


urlpatterns = [
    path("ar/products/<int:product_id>/", ProductARDataAPI.as_view()),
]

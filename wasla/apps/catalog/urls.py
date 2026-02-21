from django.urls import path

from apps.catalog.api import LowStockAPI, StockMovementsAPI


urlpatterns = [
    path("merchants/inventory/low-stock/", LowStockAPI.as_view()),
    path("merchants/inventory/movements/", StockMovementsAPI.as_view()),
]

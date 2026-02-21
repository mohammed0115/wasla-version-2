
from django.urls import path
from .views.api import OrderCreateAPI, SalesReportAPI

urlpatterns = [
    path("customers/<int:customer_id>/orders/create/", OrderCreateAPI.as_view()),
    path("merchants/sales/report/", SalesReportAPI.as_view()),
]

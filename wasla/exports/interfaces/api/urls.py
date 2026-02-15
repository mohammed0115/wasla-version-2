from django.urls import path

from .views import ExportInvoicePDFAPI, ExportOrdersCSVAPI


urlpatterns = [
    path("exports/orders.csv", ExportOrdersCSVAPI.as_view()),
    path("exports/invoice/<int:order_id>.pdf", ExportInvoicePDFAPI.as_view()),
]

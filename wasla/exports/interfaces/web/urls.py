from django.urls import path

from .views import export_invoice_pdf, export_orders_csv, exports_index


urlpatterns = [
    path("dashboard/exports", exports_index, name="dashboard_exports"),
    path("dashboard/exports/orders.csv", export_orders_csv, name="dashboard_exports_orders_csv"),
    path("dashboard/exports/invoice/<int:order_id>.pdf", export_invoice_pdf, name="dashboard_exports_invoice"),
]

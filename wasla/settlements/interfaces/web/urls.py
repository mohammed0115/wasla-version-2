from django.urls import path
from . import views

app_name = "settlements_web"

urlpatterns = [
    path("dashboard/balance", views.balance_view, name="dashboard_balance"),
    path("dashboard/settlements", views.settlement_list, name="dashboard_settlements_list"),
    path("dashboard/settlements/<int:settlement_id>", views.settlement_detail, name="dashboard_settlements_detail"),

    # Admin settlements (optional)
    path("admin/settlements", views.admin_settlement_list, name="admin_settlements_list"),
    path("admin/settlements/<int:settlement_id>", views.admin_settlement_detail, name="admin_settlements_detail"),
    path("admin/settlements/<int:settlement_id>/approve", views.admin_settlement_approve, name="admin_settlement_approve"),
    path("admin/settlements/<int:settlement_id>/mark-paid", views.admin_settlement_mark_paid, name="admin_settlement_mark_paid"),
]

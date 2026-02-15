from django.urls import path

from .views import (
    admin_settlement_approve,
    admin_settlement_detail,
    admin_settlement_list,
    admin_settlement_mark_paid,
)


urlpatterns = [
    path("", admin_settlement_list, name="admin_settlements_list"),
    path("<int:settlement_id>/", admin_settlement_detail, name="admin_settlements_detail"),
    path("<int:settlement_id>/approve", admin_settlement_approve, name="admin_settlements_approve"),
    path("<int:settlement_id>/mark-paid", admin_settlement_mark_paid, name="admin_settlements_mark_paid"),
]

from django.urls import path

from .views import (
    AdminApproveSettlementAPI,
    AdminMarkSettlementPaidAPI,
    MerchantBalanceAPI,
    MerchantInvoiceDraftAPI,
    MerchantMonthlyReportAPI,
    MerchantSettlementDetailAPI,
    MerchantSettlementsAPI,
)


urlpatterns = [
    path("balance", MerchantBalanceAPI.as_view()),
    path("settlements", MerchantSettlementsAPI.as_view()),
    path("settlements/<int:settlement_id>", MerchantSettlementDetailAPI.as_view()),
    path("settlements/monthly-report/", MerchantMonthlyReportAPI.as_view()),
    path("settlements/invoices/draft/", MerchantInvoiceDraftAPI.as_view()),
    path("admin/settlements/<int:settlement_id>/approve", AdminApproveSettlementAPI.as_view()),
    path("admin/settlements/<int:settlement_id>/mark-paid", AdminMarkSettlementPaidAPI.as_view()),
]

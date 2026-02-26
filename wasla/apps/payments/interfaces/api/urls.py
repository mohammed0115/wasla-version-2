from django.urls import path

from .views import (
    PaymentInitiateAPI,
    PaymentWebhookAPI,
    AdminPaymentEventsAPI,
    AdminPaymentRiskAPI,
    AdminPaymentRiskApproveAPI,
    AdminPaymentRiskRejectAPI,
    MerchantOrderPaymentStatusAPI,
    MerchantOrderPaymentTimelineAPI,
)


urlpatterns = [
    path("payments/initiate", PaymentInitiateAPI.as_view()),
    path("payments/webhook/<str:provider>/", PaymentWebhookAPI.as_view()),
    path("payments/webhooks/<str:provider>", PaymentWebhookAPI.as_view()),
    path("payments/webhooks/<str:provider>/", PaymentWebhookAPI.as_view()),
    path("admin/payments/events/", AdminPaymentEventsAPI.as_view()),
    path("admin/payments/risk/", AdminPaymentRiskAPI.as_view()),
    path("admin/payments/risk/<int:risk_id>/approve/", AdminPaymentRiskApproveAPI.as_view()),
    path("admin/payments/risk/<int:risk_id>/reject/", AdminPaymentRiskRejectAPI.as_view()),
    path("orders/<int:order_id>/payment-status/", MerchantOrderPaymentStatusAPI.as_view()),
    path("orders/<int:order_id>/payment-timeline/", MerchantOrderPaymentTimelineAPI.as_view()),
]

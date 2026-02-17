from django.urls import path

from .views import PaymentInitiateAPI, PaymentWebhookAPI


urlpatterns = [
    path("payments/initiate", PaymentInitiateAPI.as_view()),
    path("payments/webhooks/<str:provider_code>", PaymentWebhookAPI.as_view()),
]

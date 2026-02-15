from django.urls import path

from .views import WebhookReceiverAPI


urlpatterns = [
    path("webhooks/<str:provider_code>", WebhookReceiverAPI.as_view()),
]

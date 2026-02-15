from django.urls import path

from .views import PaymentInitiateAPI


urlpatterns = [
    path("payments/initiate", PaymentInitiateAPI.as_view()),
]

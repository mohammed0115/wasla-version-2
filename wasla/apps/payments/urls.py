
from django.urls import path
from .views.api import PaymentInitiateAPI

urlpatterns = [
    path("orders/<int:order_id>/pay/", PaymentInitiateAPI.as_view()),
]

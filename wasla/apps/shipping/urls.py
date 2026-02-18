
from django.urls import path
from .views.api import ShipmentCreateAPI

urlpatterns = [
    path("orders/<int:order_id>/ship/", ShipmentCreateAPI.as_view()),
]

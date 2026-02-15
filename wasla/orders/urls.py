
from django.urls import path
from .views.api import OrderCreateAPI

urlpatterns = [
    path("customers/<int:customer_id>/orders/create/", OrderCreateAPI.as_view()),
]

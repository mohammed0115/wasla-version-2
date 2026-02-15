
from django.urls import path
from .views.api import CustomerCreateAPI

urlpatterns = [
    path("customers/create/", CustomerCreateAPI.as_view()),
]

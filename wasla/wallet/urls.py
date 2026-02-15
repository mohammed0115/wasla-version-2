
from django.urls import path
from .views.api import WalletDetailAPI

urlpatterns = [
    path("stores/<int:store_id>/wallet/", WalletDetailAPI.as_view()),
]

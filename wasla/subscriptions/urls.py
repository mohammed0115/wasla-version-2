
from django.urls import path
from .views.api import PlanListAPI, SubscribeStoreAPI

urlpatterns = [
    path("plans/", PlanListAPI.as_view()),
    path("stores/<int:store_id>/subscribe/", SubscribeStoreAPI.as_view()),
]

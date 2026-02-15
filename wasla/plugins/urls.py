
from django.urls import path
from .views.api import PluginListAPI, PluginInstallAPI

urlpatterns = [
    path("plugins/", PluginListAPI.as_view()),
    path("stores/<int:store_id>/plugins/install/", PluginInstallAPI.as_view()),
]

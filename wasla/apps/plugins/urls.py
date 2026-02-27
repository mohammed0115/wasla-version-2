
from django.urls import path
from .views.api import (
    PluginDisableAPI,
    PluginEnableAPI,
    PluginInstallAPI,
    PluginListAPI,
    PluginUninstallAPI,
)

urlpatterns = [
    path("plugins/", PluginListAPI.as_view()),
    path("stores/<int:store_id>/plugins/install/", PluginInstallAPI.as_view()),
    path("stores/<int:store_id>/plugins/enable/", PluginEnableAPI.as_view()),
    path("stores/<int:store_id>/plugins/disable/", PluginDisableAPI.as_view()),
    path("stores/<int:store_id>/plugins/uninstall/", PluginUninstallAPI.as_view()),
]

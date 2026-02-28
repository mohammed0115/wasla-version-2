
from django.urls import path
from .views.api import (
    PluginDisableAPI,
    PluginEnableAPI,
    PluginEventSubscriptionListCreateAPI,
    PluginEventSubscriptionToggleAPI,
    PluginInstallAPI,
    PluginListAPI,
    PluginRegistryDetailAPI,
    PluginRegistryListCreateAPI,
    PluginScopeDeleteAPI,
    PluginScopeListCreateAPI,
    PluginUninstallAPI,
)

urlpatterns = [
    path("plugins/", PluginListAPI.as_view()),
    path("plugins/registry/", PluginRegistryListCreateAPI.as_view()),
    path("plugins/registry/<int:registration_id>/", PluginRegistryDetailAPI.as_view()),
    path("plugins/<int:plugin_id>/scopes/", PluginScopeListCreateAPI.as_view()),
    path("plugins/scopes/<int:scope_id>/", PluginScopeDeleteAPI.as_view()),
    path("stores/<int:store_id>/plugins/install/", PluginInstallAPI.as_view()),
    path("stores/<int:store_id>/plugins/enable/", PluginEnableAPI.as_view()),
    path("stores/<int:store_id>/plugins/disable/", PluginDisableAPI.as_view()),
    path("stores/<int:store_id>/plugins/uninstall/", PluginUninstallAPI.as_view()),
    path("stores/<int:store_id>/plugins/event-subscriptions/", PluginEventSubscriptionListCreateAPI.as_view()),
    path("stores/<int:store_id>/plugins/event-subscriptions/<int:subscription_id>/", PluginEventSubscriptionToggleAPI.as_view()),
]

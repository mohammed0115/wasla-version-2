
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils.decorators import method_decorator
from ..models import Plugin
from ..services.plugin_service import PluginService
from ..services.installation_service import PluginInstallationService
from ..services.lifecycle_service import PluginLifecycleService
from ..serializers import PluginSerializer, InstalledPluginSerializer
from apps.security.rbac import require_permission
from apps.tenants.guards import require_store, require_tenant

class PluginListAPI(APIView):
    @method_decorator(require_permission("plugins.view_plugins"))
    def get(self, request):
        plugins = PluginService.list_available_plugins()
        return Response(PluginSerializer(plugins, many=True).data)

class PluginInstallAPI(APIView):
    @method_decorator(require_permission("plugins.install_plugin"))
    def post(self, request, store_id):
        store = require_store(request)
        tenant = require_tenant(request)
        if int(store_id) != int(store.id):
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        plugin = Plugin.objects.filter(id=request.data.get("plugin_id")).first()
        if not plugin:
            return Response({"detail": "Plugin not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            installed = PluginInstallationService.install_plugin(
                store.id,
                plugin,
                actor_user_id=request.user.id if request.user.is_authenticated else None,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InstalledPluginSerializer(installed).data, status=status.HTTP_201_CREATED)


class PluginEnableAPI(APIView):
    @method_decorator(require_permission("plugins.enable_plugin"))
    def post(self, request, store_id):
        store = require_store(request)
        require_tenant(request)
        if int(store_id) != int(store.id):
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        plugin = Plugin.objects.filter(id=request.data.get("plugin_id")).first()
        if not plugin:
            return Response({"detail": "Plugin not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            installed = PluginLifecycleService.enable_plugin(
                store_id=store.id,
                plugin=plugin,
                actor_user_id=request.user.id if request.user.is_authenticated else None,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InstalledPluginSerializer(installed).data, status=status.HTTP_200_OK)


class PluginDisableAPI(APIView):
    @method_decorator(require_permission("plugins.disable_plugin"))
    def post(self, request, store_id):
        store = require_store(request)
        require_tenant(request)
        if int(store_id) != int(store.id):
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        plugin = Plugin.objects.filter(id=request.data.get("plugin_id")).first()
        if not plugin:
            return Response({"detail": "Plugin not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            installed = PluginLifecycleService.disable_plugin(
                store_id=store.id,
                plugin=plugin,
                actor_user_id=request.user.id if request.user.is_authenticated else None,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InstalledPluginSerializer(installed).data, status=status.HTTP_200_OK)


class PluginUninstallAPI(APIView):
    @method_decorator(require_permission("plugins.uninstall_plugin"))
    def post(self, request, store_id):
        store = require_store(request)
        require_tenant(request)
        if int(store_id) != int(store.id):
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        plugin = Plugin.objects.filter(id=request.data.get("plugin_id")).first()
        if not plugin:
            return Response({"detail": "Plugin not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            installed = PluginLifecycleService.uninstall_plugin(
                store_id=store.id,
                plugin=plugin,
                actor_user_id=request.user.id if request.user.is_authenticated else None,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InstalledPluginSerializer(installed).data, status=status.HTTP_200_OK)

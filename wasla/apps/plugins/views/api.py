
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..models import Plugin
from ..services.plugin_service import PluginService
from ..services.installation_service import PluginInstallationService
from ..serializers import PluginSerializer, InstalledPluginSerializer

class PluginListAPI(APIView):
    def get(self, request):
        plugins = PluginService.list_available_plugins()
        return Response(PluginSerializer(plugins, many=True).data)

class PluginInstallAPI(APIView):
    def post(self, request, store_id):
        plugin = Plugin.objects.get(id=request.data.get("plugin_id"))
        installed = PluginInstallationService.install_plugin(store_id, plugin)
        return Response(InstalledPluginSerializer(installed).data, status=status.HTTP_201_CREATED)

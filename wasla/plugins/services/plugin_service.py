
from ..models import Plugin

class PluginService:
    @staticmethod
    def list_available_plugins():
        return Plugin.objects.filter(is_active=True)

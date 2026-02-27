
from .lifecycle_service import PluginLifecycleService

class PluginInstallationService:
    @staticmethod
    def install_plugin(store_id, plugin, actor_user_id=None):
        return PluginLifecycleService.install_plugin(
            store_id=store_id,
            plugin=plugin,
            actor_user_id=actor_user_id,
        )

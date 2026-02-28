from __future__ import annotations

from apps.plugins.models import Plugin


class PluginSecurityScopeService:
    @staticmethod
    def has_scope(*, plugin: Plugin, scope_code: str) -> bool:
        scope = (scope_code or "").strip()
        if not scope:
            return False
        return plugin.permission_scopes.filter(scope_code=scope).exists()

    @staticmethod
    def require_scope(*, plugin: Plugin, scope_code: str) -> None:
        if not PluginSecurityScopeService.has_scope(plugin=plugin, scope_code=scope_code):
            raise ValueError(f"Plugin '{plugin.name}' lacks required scope '{scope_code}'")

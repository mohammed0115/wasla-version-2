from __future__ import annotations

from django.db import transaction

from apps.plugins.models import InstalledPlugin, Plugin, PluginActivationLog
from apps.stores.models import Store
from apps.subscriptions.services.feature_policy import FeaturePolicy
from apps.subscriptions.services.subscription_service import SubscriptionService


class PluginLifecycleService:
    @staticmethod
    def _resolve_tenant_id(store_id: int) -> int | None:
        return Store.objects.filter(id=store_id).values_list("tenant_id", flat=True).first()

    @staticmethod
    def _ensure_install_record(*, store_id: int, plugin: Plugin, tenant_id: int | None) -> InstalledPlugin:
        installed, _ = InstalledPlugin.objects.get_or_create(
            store_id=store_id,
            plugin=plugin,
            defaults={
                "tenant_id": tenant_id,
                "status": "installed",
            },
        )
        updates: list[str] = []
        if installed.tenant_id != tenant_id:
            installed.tenant_id = tenant_id
            updates.append("tenant_id")
        if installed.status == "uninstalled":
            installed.status = "installed"
            updates.append("status")
        if updates:
            installed.save(update_fields=updates)
        return installed

    @staticmethod
    def _check_plan_feature_gate(*, store_id: int, plugin: Plugin) -> None:
        subscription = SubscriptionService.get_active_subscription(store_id)
        if not subscription:
            raise ValueError("No active subscription")

        if not FeaturePolicy.can_use(subscription, "plugins"):
            raise ValueError("Plugins not allowed for this plan")

        required_feature = (plugin.required_feature or "plugins").strip().lower()
        if required_feature and not FeaturePolicy.can_use(subscription, required_feature):
            raise ValueError(f"Plugin requires feature '{required_feature}'")

    @staticmethod
    def _check_dependencies_for_enable(*, store_id: int, plugin: Plugin) -> None:
        dependency_ids = list(plugin.dependencies.values_list("id", flat=True))
        if not dependency_ids:
            return

        active_ids = set(
            InstalledPlugin.objects.filter(
                store_id=store_id,
                plugin_id__in=dependency_ids,
                status="active",
            ).values_list("plugin_id", flat=True)
        )
        missing_ids = [plugin_id for plugin_id in dependency_ids if plugin_id not in active_ids]
        if not missing_ids:
            return

        missing_names = list(Plugin.objects.filter(id__in=missing_ids).values_list("name", flat=True))
        raise ValueError(f"Missing active dependencies: {', '.join(missing_names)}")

    @staticmethod
    def _assert_can_uninstall(*, store_id: int, plugin: Plugin) -> None:
        dependent_ids = list(plugin.dependents.values_list("id", flat=True))
        if not dependent_ids:
            return

        blocking = InstalledPlugin.objects.filter(
            store_id=store_id,
            plugin_id__in=dependent_ids,
            status__in=["installed", "active", "disabled"],
        ).select_related("plugin")
        if not blocking.exists():
            return

        blocking_names = sorted({item.plugin.name for item in blocking})
        raise ValueError(f"Cannot uninstall; dependent plugins exist: {', '.join(blocking_names)}")

    @staticmethod
    def _log_activation(*, installed: InstalledPlugin, action: str, actor_user_id: int | None = None, metadata_json: dict | None = None) -> None:
        PluginActivationLog.objects.create(
            plugin=installed.plugin,
            installed_plugin=installed,
            tenant_id=installed.tenant_id,
            store_id=installed.store_id,
            action=action,
            actor_user_id=actor_user_id,
            metadata_json=metadata_json or {},
        )

    @staticmethod
    @transaction.atomic
    def install_plugin(*, store_id: int, plugin: Plugin, actor_user_id: int | None = None) -> InstalledPlugin:
        tenant_id = PluginLifecycleService._resolve_tenant_id(store_id)
        installed = PluginLifecycleService._ensure_install_record(store_id=store_id, plugin=plugin, tenant_id=tenant_id)
        return PluginLifecycleService.enable_plugin(store_id=store_id, plugin=plugin, actor_user_id=actor_user_id)

    @staticmethod
    @transaction.atomic
    def enable_plugin(*, store_id: int, plugin: Plugin, actor_user_id: int | None = None) -> InstalledPlugin:
        if not plugin.is_active:
            raise ValueError("Plugin is not active")

        PluginLifecycleService._check_plan_feature_gate(store_id=store_id, plugin=plugin)
        PluginLifecycleService._check_dependencies_for_enable(store_id=store_id, plugin=plugin)

        tenant_id = PluginLifecycleService._resolve_tenant_id(store_id)
        installed = PluginLifecycleService._ensure_install_record(store_id=store_id, plugin=plugin, tenant_id=tenant_id)

        if installed.status != "active":
            installed.status = "active"
            installed.save(update_fields=["status"])
            PluginLifecycleService._log_activation(installed=installed, action=PluginActivationLog.ACTION_ENABLE, actor_user_id=actor_user_id)

        return installed

    @staticmethod
    @transaction.atomic
    def disable_plugin(*, store_id: int, plugin: Plugin, actor_user_id: int | None = None) -> InstalledPlugin:
        installed = InstalledPlugin.objects.filter(store_id=store_id, plugin=plugin).first()
        if not installed or installed.status == "uninstalled":
            raise ValueError("Plugin is not installed")

        if installed.status != "disabled":
            installed.status = "disabled"
            installed.save(update_fields=["status"])
            PluginLifecycleService._log_activation(installed=installed, action=PluginActivationLog.ACTION_DISABLE, actor_user_id=actor_user_id)

        return installed

    @staticmethod
    @transaction.atomic
    def uninstall_plugin(*, store_id: int, plugin: Plugin, actor_user_id: int | None = None) -> InstalledPlugin:
        installed = InstalledPlugin.objects.filter(store_id=store_id, plugin=plugin).first()
        if not installed or installed.status == "uninstalled":
            raise ValueError("Plugin is not installed")

        PluginLifecycleService._assert_can_uninstall(store_id=store_id, plugin=plugin)

        if installed.status == "active":
            installed.status = "disabled"
            installed.save(update_fields=["status"])
            PluginLifecycleService._log_activation(
                installed=installed,
                action=PluginActivationLog.ACTION_DISABLE,
                actor_user_id=actor_user_id,
                metadata_json={"reason": "uninstall"},
            )

        installed.status = "uninstalled"
        installed.save(update_fields=["status"])
        return installed

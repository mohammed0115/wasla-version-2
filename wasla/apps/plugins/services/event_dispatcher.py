from __future__ import annotations

from django.db import transaction

from apps.plugins.models import InstalledPlugin, PluginEventDelivery, PluginEventSubscription
from apps.plugins.services.security_scope_service import PluginSecurityScopeService
from apps.plugins.services.version_compatibility_service import PluginVersionCompatibilityService


class PluginEventDispatcher:
    """Safe multi-tenant plugin event dispatcher (persistence-first)."""

    @staticmethod
    @transaction.atomic
    def dispatch_event(*, tenant_id: int, event_key: str, payload: dict | None = None) -> list[PluginEventDelivery]:
        event = (event_key or "").strip()
        if not event:
            raise ValueError("event_key is required")

        payload_json = payload or {}
        deliveries: list[PluginEventDelivery] = []

        subscriptions = (
            PluginEventSubscription.objects.select_related("installed_plugin", "installed_plugin__plugin")
            .filter(
                tenant_id=tenant_id,
                event_key=event,
                is_active=True,
                installed_plugin__status="active",
            )
        )

        for sub in subscriptions:
            installed = sub.installed_plugin
            plugin = installed.plugin

            try:
                PluginVersionCompatibilityService.assert_compatible(plugin)
                PluginSecurityScopeService.require_scope(plugin=plugin, scope_code=f"events.consume.{event}")
                delivery_status = PluginEventDelivery.STATUS_QUEUED
                error_message = ""
            except Exception as exc:
                delivery_status = PluginEventDelivery.STATUS_SKIPPED
                error_message = str(exc)[:255]

            delivery = PluginEventDelivery.objects.create(
                plugin=plugin,
                installed_plugin=installed,
                tenant_id=tenant_id,
                event_key=event,
                payload_json=payload_json,
                status=delivery_status,
                error_message=error_message,
            )
            deliveries.append(delivery)

        return deliveries

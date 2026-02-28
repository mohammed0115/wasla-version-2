from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings

from apps.plugins.models import Plugin, PluginActivationLog
from apps.plugins.models import PluginEventSubscription, PluginPermissionScope, PluginRegistration
from apps.plugins.services.event_dispatcher import PluginEventDispatcher
from apps.plugins.services.lifecycle_service import PluginLifecycleService
from apps.stores.models import Store
from apps.subscriptions.models import StoreSubscription, SubscriptionPlan
from apps.tenants.models import Tenant


class PluginLifecycleServiceTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        User = get_user_model()
        self.owner = User.objects.create_user(username="plugins-owner", password="pass12345")
        self.tenant = Tenant.objects.create(slug="plugins-tenant", name="Plugins Tenant", is_active=True)
        self.store = Store.objects.create(
            owner=self.owner,
            tenant=self.tenant,
            name="Plugins Store",
            slug="plugins-store",
            subdomain="plugins-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

    def _activate_plan(self, *, features: list[str]):
        plan = SubscriptionPlan.objects.create(
            name=f"Plan-{len(features)}-{SubscriptionPlan.objects.count()}",
            price="99.00",
            billing_cycle="monthly",
            features=features,
            is_active=True,
        )
        StoreSubscription.objects.filter(store_id=self.store.id, status="active").update(status="expired")
        StoreSubscription.objects.create(
            store_id=self.store.id,
            plan=plan,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=365),
            status="active",
        )

    def test_enable_fails_when_required_plan_feature_missing(self):
        self._activate_plan(features=["plugins"])
        plugin = Plugin.objects.create(
            name="Advanced Analytics Plugin",
            version="1.0.0",
            provider="wasla",
            required_feature="advanced_plugins",
            is_active=True,
        )
        PluginRegistration.objects.create(
            plugin=plugin,
            plugin_key="advanced-analytics",
            entrypoint="plugins.advanced_analytics:Plugin",
            min_core_version="1.0.0",
            verified=True,
        )
        PluginPermissionScope.objects.create(plugin=plugin, scope_code="plugin.lifecycle.enable")

        with self.assertRaisesMessage(ValueError, "Plugin requires feature 'advanced_plugins'"):
            PluginLifecycleService.enable_plugin(store_id=self.store.id, plugin=plugin, actor_user_id=self.owner.id)

    def test_uninstall_fails_when_active_dependents_exist(self):
        self._activate_plan(features=["plugins"])
        base_plugin = Plugin.objects.create(
            name="Core Payments Connector",
            version="1.0.0",
            provider="wasla",
            required_feature="plugins",
            is_active=True,
        )
        dependent_plugin = Plugin.objects.create(
            name="Advanced Settlement Adapter",
            version="1.0.0",
            provider="wasla",
            required_feature="plugins",
            is_active=True,
        )
        PluginRegistration.objects.create(
            plugin=base_plugin,
            plugin_key="core-payments",
            entrypoint="plugins.core_payments:Plugin",
            min_core_version="1.0.0",
            verified=True,
        )
        PluginRegistration.objects.create(
            plugin=dependent_plugin,
            plugin_key="advanced-settlement",
            entrypoint="plugins.advanced_settlement:Plugin",
            min_core_version="1.0.0",
            verified=True,
        )
        PluginPermissionScope.objects.bulk_create(
            [
                PluginPermissionScope(plugin=base_plugin, scope_code="plugin.lifecycle.enable"),
                PluginPermissionScope(plugin=base_plugin, scope_code="plugin.lifecycle.disable"),
                PluginPermissionScope(plugin=base_plugin, scope_code="plugin.lifecycle.uninstall"),
                PluginPermissionScope(plugin=dependent_plugin, scope_code="plugin.lifecycle.enable"),
                PluginPermissionScope(plugin=dependent_plugin, scope_code="plugin.lifecycle.disable"),
                PluginPermissionScope(plugin=dependent_plugin, scope_code="plugin.lifecycle.uninstall"),
            ]
        )
        dependent_plugin.dependencies.add(base_plugin)

        PluginLifecycleService.install_plugin(store_id=self.store.id, plugin=base_plugin, actor_user_id=self.owner.id)
        PluginLifecycleService.install_plugin(store_id=self.store.id, plugin=dependent_plugin, actor_user_id=self.owner.id)

        with self.assertRaisesMessage(ValueError, "Cannot uninstall; dependent plugins exist"):
            PluginLifecycleService.uninstall_plugin(
                store_id=self.store.id,
                plugin=base_plugin,
                actor_user_id=self.owner.id,
            )

    def test_enable_and_disable_are_logged(self):
        self._activate_plan(features=["plugins"])
        plugin = Plugin.objects.create(
            name="Shipping Label Plugin",
            version="1.0.0",
            provider="wasla",
            required_feature="plugins",
            is_active=True,
        )
        PluginRegistration.objects.create(
            plugin=plugin,
            plugin_key="shipping-label",
            entrypoint="plugins.shipping_label:Plugin",
            min_core_version="1.0.0",
            verified=True,
        )
        PluginPermissionScope.objects.bulk_create(
            [
                PluginPermissionScope(plugin=plugin, scope_code="plugin.lifecycle.enable"),
                PluginPermissionScope(plugin=plugin, scope_code="plugin.lifecycle.disable"),
                PluginPermissionScope(plugin=plugin, scope_code="plugin.lifecycle.uninstall"),
            ]
        )

        installed = PluginLifecycleService.install_plugin(
            store_id=self.store.id,
            plugin=plugin,
            actor_user_id=self.owner.id,
        )
        self.assertEqual(installed.status, "active")

        enable_logs = PluginActivationLog.objects.filter(
            plugin=plugin,
            store_id=self.store.id,
            action=PluginActivationLog.ACTION_ENABLE,
        )
        self.assertEqual(enable_logs.count(), 1)

        PluginLifecycleService.disable_plugin(
            store_id=self.store.id,
            plugin=plugin,
            actor_user_id=self.owner.id,
        )

        disable_logs = PluginActivationLog.objects.filter(
            plugin=plugin,
            store_id=self.store.id,
            action=PluginActivationLog.ACTION_DISABLE,
        )
        self.assertEqual(disable_logs.count(), 1)

    def test_enable_fails_without_verified_registration(self):
        self._activate_plan(features=["plugins"])
        plugin = Plugin.objects.create(
            name="Unverified Plugin",
            version="1.0.0",
            provider="wasla",
            required_feature="plugins",
            is_active=True,
        )
        PluginRegistration.objects.create(
            plugin=plugin,
            plugin_key="unverified-plugin",
            entrypoint="plugins.unverified:Plugin",
            min_core_version="1.0.0",
            verified=False,
        )
        PluginPermissionScope.objects.create(plugin=plugin, scope_code="plugin.lifecycle.enable")

        with self.assertRaisesMessage(ValueError, "Plugin registration is not verified"):
            PluginLifecycleService.enable_plugin(store_id=self.store.id, plugin=plugin, actor_user_id=self.owner.id)

    @override_settings(APP_VERSION="1.0.0")
    def test_event_dispatcher_is_tenant_isolated_and_scope_enforced(self):
        self._activate_plan(features=["plugins"])
        plugin = Plugin.objects.create(
            name="Order Hooks",
            version="1.0.0",
            provider="wasla",
            required_feature="plugins",
            is_active=True,
        )
        PluginRegistration.objects.create(
            plugin=plugin,
            plugin_key="order-hooks",
            entrypoint="plugins.order_hooks:Plugin",
            min_core_version="1.0.0",
            verified=True,
        )
        PluginPermissionScope.objects.bulk_create(
            [
                PluginPermissionScope(plugin=plugin, scope_code="plugin.lifecycle.enable"),
                PluginPermissionScope(plugin=plugin, scope_code="events.consume.order.created"),
            ]
        )
        installed = PluginLifecycleService.install_plugin(
            store_id=self.store.id,
            plugin=plugin,
            actor_user_id=self.owner.id,
        )
        PluginEventSubscription.objects.create(
            installed_plugin=installed,
            tenant_id=self.tenant.id,
            event_key="order.created",
            is_active=True,
        )

        deliveries = PluginEventDispatcher.dispatch_event(
            tenant_id=self.tenant.id,
            event_key="order.created",
            payload={"order_id": 123},
        )
        self.assertEqual(len(deliveries), 1)
        self.assertEqual(deliveries[0].status, "queued")

        other_tenant = Tenant.objects.create(slug="other-tenant", name="Other", is_active=True)
        other_deliveries = PluginEventDispatcher.dispatch_event(
            tenant_id=other_tenant.id,
            event_key="order.created",
            payload={"order_id": 555},
        )
        self.assertEqual(other_deliveries, [])

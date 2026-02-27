from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.plugins.models import Plugin, PluginActivationLog
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

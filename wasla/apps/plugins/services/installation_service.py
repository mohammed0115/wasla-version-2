
from django.db import transaction
from ..models import InstalledPlugin
from apps.subscriptions.services.subscription_service import SubscriptionService
from apps.subscriptions.services.feature_policy import FeaturePolicy
from apps.stores.models import Store

class PluginInstallationService:
    @staticmethod
    @transaction.atomic
    def install_plugin(store_id, plugin):
        tenant_id = (
            Store.objects.filter(id=store_id)
            .values_list("tenant_id", flat=True)
            .first()
        )
        subscription = SubscriptionService.get_active_subscription(store_id)
        if not subscription:
            raise ValueError("No active subscription")

        if not FeaturePolicy.can_use(subscription, "plugins"):
            raise ValueError("Plugins not allowed for this plan")

        installed, created = InstalledPlugin.objects.get_or_create(
            tenant_id=tenant_id,
            store_id=store_id,
            plugin=plugin,
            defaults={"status": "installed"}
        )
        if not created:
            raise ValueError("Plugin already installed")

        installed.status = "active"
        installed.save(update_fields=["status"])
        return installed

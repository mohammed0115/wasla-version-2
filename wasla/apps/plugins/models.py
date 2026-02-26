"""
Plugins models (MVP).

AR:
- تعريف الإضافات المتاحة على مستوى المنصة.
- ربط الإضافات المثبتة بكل متجر عبر InstalledPlugin.

EN:
- Defines platform-level plugins.
- Tracks per-store installations via InstalledPlugin.
"""

from django.db import models

from apps.tenants.managers import TenantManager


class Plugin(models.Model):
    """Plugin metadata available in the app store."""

    name = models.CharField(max_length=100, unique=True)
    version = models.CharField(max_length=20)
    provider = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    required_feature = models.CharField(max_length=80, default="plugins")
    dependencies = models.ManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="dependents",
    )
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class InstalledPlugin(models.Model):
    """Installed plugin for a specific store (tenant)."""
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"

    STATUS_CHOICES = [
        ("installed", "Installed"),
        ("active", "Active"),
        ("disabled", "Disabled"),
        ("uninstalled", "Uninstalled"),
    ]
    plugin = models.ForeignKey(Plugin, on_delete=models.PROTECT)
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    store_id = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    installed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.plugin} (store {self.store_id})"

    class Meta:
        unique_together = ("plugin", "store_id")


class PluginActivationLog(models.Model):
    """Tracks plugin activation/deactivation lifecycle events."""

    ACTION_ENABLE = "enabled"
    ACTION_DISABLE = "disabled"

    ACTION_CHOICES = [
        (ACTION_ENABLE, "Enabled"),
        (ACTION_DISABLE, "Disabled"),
    ]

    plugin = models.ForeignKey(Plugin, on_delete=models.PROTECT, related_name="activation_logs")
    installed_plugin = models.ForeignKey(
        InstalledPlugin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activation_logs",
    )
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    store_id = models.IntegerField(db_index=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    actor_user_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata_json = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "created_at"]),
            models.Index(fields=["tenant_id", "created_at"]),
            models.Index(fields=["plugin", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"plugin={self.plugin_id} store={self.store_id} action={self.action}"

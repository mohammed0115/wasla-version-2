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


class PluginRegistration(models.Model):
    """Plugin runtime registration and compatibility contract."""

    ISOLATION_PROCESS = "process"
    ISOLATION_SANDBOX = "sandbox"

    ISOLATION_CHOICES = [
        (ISOLATION_PROCESS, "Process"),
        (ISOLATION_SANDBOX, "Sandbox"),
    ]

    plugin = models.OneToOneField(Plugin, on_delete=models.CASCADE, related_name="registration")
    plugin_key = models.CharField(max_length=120, unique=True)
    entrypoint = models.CharField(max_length=255)
    min_core_version = models.CharField(max_length=32, default="0.0.0")
    max_core_version = models.CharField(max_length=32, blank=True, default="")
    isolation_mode = models.CharField(max_length=20, choices=ISOLATION_CHOICES, default=ISOLATION_SANDBOX)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["plugin_key"]),
            models.Index(fields=["verified"]),
        ]

    def __str__(self) -> str:
        return f"{self.plugin_key} ({self.plugin_id})"


class PluginPermissionScope(models.Model):
    """Explicit allowed scopes for a plugin; deny-by-default."""

    plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE, related_name="permission_scopes")
    scope_code = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("plugin", "scope_code"), name="uq_plugin_scope_code"),
        ]
        indexes = [
            models.Index(fields=["scope_code"]),
        ]

    def __str__(self) -> str:
        return f"{self.plugin_id}:{self.scope_code}"


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


class PluginEventSubscription(models.Model):
    """Per-tenant event subscription for active installed plugins."""

    installed_plugin = models.ForeignKey(
        InstalledPlugin,
        on_delete=models.CASCADE,
        related_name="event_subscriptions",
    )
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    event_key = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("installed_plugin", "event_key"),
                name="uq_plugin_event_subscription",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant_id", "event_key"]),
        ]

    def __str__(self) -> str:
        return f"{self.installed_plugin_id}:{self.event_key}"


class PluginEventDelivery(models.Model):
    """Event delivery records for traceability and retry pipelines."""

    STATUS_QUEUED = "queued"
    STATUS_DELIVERED = "delivered"
    STATUS_SKIPPED = "skipped"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_SKIPPED, "Skipped"),
        (STATUS_FAILED, "Failed"),
    ]

    plugin = models.ForeignKey(Plugin, on_delete=models.PROTECT, related_name="event_deliveries")
    installed_plugin = models.ForeignKey(
        InstalledPlugin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="event_deliveries",
    )
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    event_key = models.CharField(max_length=120)
    payload_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    error_message = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "event_key", "created_at"]),
            models.Index(fields=["plugin", "status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"plugin={self.plugin_id} event={self.event_key} status={self.status}"


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

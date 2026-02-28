# Generated manually for scalable plugin framework architecture

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("plugins", "0002_pluginactivationlog_and_lifecycle_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="PluginRegistration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("plugin_key", models.CharField(max_length=120, unique=True)),
                ("entrypoint", models.CharField(max_length=255)),
                ("min_core_version", models.CharField(default="0.0.0", max_length=32)),
                ("max_core_version", models.CharField(blank=True, default="", max_length=32)),
                (
                    "isolation_mode",
                    models.CharField(
                        choices=[("process", "Process"), ("sandbox", "Sandbox")],
                        default="sandbox",
                        max_length=20,
                    ),
                ),
                ("verified", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "plugin",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="registration", to="plugins.plugin"),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="pluginregistration",
            index=models.Index(fields=["plugin_key"], name="plugins_plu_plugin__630556_idx"),
        ),
        migrations.AddIndex(
            model_name="pluginregistration",
            index=models.Index(fields=["verified"], name="plugins_plu_verifie_13a846_idx"),
        ),
        migrations.CreateModel(
            name="PluginPermissionScope",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scope_code", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "plugin",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="permission_scopes", to="plugins.plugin"),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="pluginpermissionscope",
            constraint=models.UniqueConstraint(fields=("plugin", "scope_code"), name="uq_plugin_scope_code"),
        ),
        migrations.AddIndex(
            model_name="pluginpermissionscope",
            index=models.Index(fields=["scope_code"], name="plugins_plu_scope_c_4ccadf_idx"),
        ),
        migrations.CreateModel(
            name="PluginEventSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tenant_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("event_key", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "installed_plugin",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="event_subscriptions", to="plugins.installedplugin"),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="plugineventsubscription",
            constraint=models.UniqueConstraint(fields=("installed_plugin", "event_key"), name="uq_plugin_event_subscription"),
        ),
        migrations.AddIndex(
            model_name="plugineventsubscription",
            index=models.Index(fields=["tenant_id", "event_key"], name="plugins_plu_tenant__355648_idx"),
        ),
        migrations.CreateModel(
            name="PluginEventDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tenant_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("event_key", models.CharField(max_length=120)),
                ("payload_json", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[("queued", "Queued"), ("delivered", "Delivered"), ("skipped", "Skipped"), ("failed", "Failed")],
                        default="queued",
                        max_length=20,
                    ),
                ),
                ("error_message", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "installed_plugin",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="event_deliveries",
                        to="plugins.installedplugin",
                    ),
                ),
                (
                    "plugin",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="event_deliveries", to="plugins.plugin"),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="plugineventdelivery",
            index=models.Index(fields=["tenant_id", "event_key", "created_at"], name="plugins_plu_tenant__37bf3f_idx"),
        ),
        migrations.AddIndex(
            model_name="plugineventdelivery",
            index=models.Index(fields=["plugin", "status", "created_at"], name="plugins_plu_plugin__fc0167_idx"),
        ),
    ]

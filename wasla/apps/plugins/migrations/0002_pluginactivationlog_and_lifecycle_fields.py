# Generated manually for plugin lifecycle management

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("plugins", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="plugin",
            name="required_feature",
            field=models.CharField(default="plugins", max_length=80),
        ),
        migrations.AddField(
            model_name="plugin",
            name="dependencies",
            field=models.ManyToManyField(blank=True, related_name="dependents", to="plugins.plugin"),
        ),
        migrations.AddField(
            model_name="installedplugin",
            name="tenant_id",
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.CreateModel(
            name="PluginActivationLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tenant_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("store_id", models.IntegerField(db_index=True)),
                (
                    "action",
                    models.CharField(
                        choices=[("enabled", "Enabled"), ("disabled", "Disabled")],
                        max_length=20,
                    ),
                ),
                ("actor_user_id", models.IntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("metadata_json", models.JSONField(blank=True, default=dict)),
                (
                    "installed_plugin",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="activation_logs",
                        to="plugins.installedplugin",
                    ),
                ),
                (
                    "plugin",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="activation_logs",
                        to="plugins.plugin",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="pluginactivationlog",
            index=models.Index(fields=["store_id", "created_at"], name="plugins_plu_store_i_3b7308_idx"),
        ),
        migrations.AddIndex(
            model_name="pluginactivationlog",
            index=models.Index(fields=["tenant_id", "created_at"], name="plugins_plu_tenant__7e2ffa_idx"),
        ),
        migrations.AddIndex(
            model_name="pluginactivationlog",
            index=models.Index(fields=["plugin", "created_at"], name="plugins_plu_plugin__029f36_idx"),
        ),
    ]

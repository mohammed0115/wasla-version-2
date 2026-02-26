# Generated migrations for domain monitoring

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DomainHealth",
            fields=[
                (
                    "store_domain",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="health_status",
                        serialize=False,
                        to="tenants.storedomain",
                    ),
                ),
                ("dns_resolves", models.BooleanField(default=False)),
                ("http_reachable", models.BooleanField(default=False)),
                ("ssl_valid", models.BooleanField(default=False)),
                ("ssl_expires_at", models.DateTimeField(blank=True, null=True)),
                ("days_until_expiry", models.IntegerField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("HEALTHY", "Healthy"),
                            ("WARNING", "Warning"),
                            ("ERROR", "Error"),
                        ],
                        db_index=True,
                        default="HEALTHY",
                        max_length=20,
                    ),
                ),
                ("last_checked_at", models.DateTimeField(auto_now_add=True)),
                ("last_error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="domain_health_records",
                        to="tenants.tenant",
                        db_index=True,
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Domain Health Records",
            },
        ),
        migrations.CreateModel(
            name="DomainAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("INFO", "Informational"),
                            ("WARNING", "Warning"),
                            ("CRITICAL", "Critical"),
                        ],
                        db_index=True,
                        default="WARNING",
                        max_length=20,
                    ),
                ),
                ("message", models.TextField()),
                ("resolution_text", models.TextField(blank=True, default="")),
                ("resolved", models.BooleanField(db_index=True, default=False)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_by", models.CharField(blank=True, default="", max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "store_domain",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alerts",
                        to="tenants.storedomain",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="domain_alerts",
                        to="tenants.tenant",
                        db_index=True,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="domainhealth",
            index=models.Index(fields=["tenant", "status"], name="domhealth_tenant_status_idx"),
        ),
        migrations.AddIndex(
            model_name="domainhealth",
            index=models.Index(fields=["status", "last_checked_at"], name="domhealth_status_checked_idx"),
        ),
        migrations.AddIndex(
            model_name="domainhealth",
            index=models.Index(fields=["ssl_expires_at"], name="domhealth_ssl_expiry_idx"),
        ),
        migrations.AddIndex(
            model_name="domainalert",
            index=models.Index(fields=["tenant", "resolved"], name="domalert_tenant_resolved_idx"),
        ),
        migrations.AddIndex(
            model_name="domainalert",
            index=models.Index(fields=["severity", "created_at"], name="domalert_severity_created_idx"),
        ),
        migrations.AddIndex(
            model_name="domainalert",
            index=models.Index(fields=["store_domain", "resolved"], name="domalert_domain_resolved_idx"),
        ),
    ]

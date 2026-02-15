from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0009_tenant_publication_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="StoreDomain",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("domain", models.CharField(max_length=255, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("VERIFYING", "Verifying"),
                            ("ACTIVE", "Active"),
                            ("FAILED", "Failed"),
                            ("DISABLED", "Disabled"),
                        ],
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("verification_token", models.CharField(blank=True, default="", max_length=128)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("ssl_cert_path", models.TextField(blank=True, default="")),
                ("ssl_key_path", models.TextField(blank=True, default="")),
                ("last_check_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="custom_domains",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["domain"], name="storedomain_domain_idx"),
                    models.Index(fields=["tenant", "status"], name="storedomain_tenant_status_idx"),
                    models.Index(fields=["status", "last_check_at"], name="storedomain_status_check_idx"),
                ],
            },
        ),
    ]

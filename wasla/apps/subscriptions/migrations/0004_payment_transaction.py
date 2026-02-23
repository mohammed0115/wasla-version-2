# Generated manually for manual subscription payments

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0003_seed_default_plans"),
        ("tenants", "0011_store_domain_status_updates"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(default="SAR", max_length=10)),
                ("method", models.CharField(default="manual", max_length=30)),
                ("reference", models.CharField(blank=True, default="", max_length=120)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("paid", "Paid"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payment_transactions",
                        to="subscriptions.subscriptionplan",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="recorded_payment_transactions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="payment_transactions",
                        to="subscriptions.storesubscription",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_transactions",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["tenant", "status", "created_at"], name="sub_pay_tenant_status_created_idx"),
                    models.Index(fields=["status", "created_at"], name="sub_pay_status_created_idx"),
                ],
            },
        ),
    ]

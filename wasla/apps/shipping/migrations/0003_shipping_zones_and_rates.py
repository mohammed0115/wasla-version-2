"""Add ShippingZone and ShippingRate models."""

from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("shipping", "0002_shipment_tenant_id"),
        ("stores", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShippingZone",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                ("countries", models.CharField(max_length=500)),
                (
                    "priority",
                    models.PositiveSmallIntegerField(
                        default=100,
                        help_text="Lower number = higher priority",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(default=True),
                ),
                (
                    "free_shipping_threshold",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=10,
                        null=True,
                        help_text="Order total for free shipping",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="stores.store",
                    ),
                ),
            ],
            options={
                "db_table": "shipping_zones",
                "indexes": [
                    models.Index(
                        fields=["store", "is_active"],
                        name="shipping_zones_store_active_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ShippingRate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "min_weight",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=10,
                        help_text="Minimum weight in kg",
                    ),
                ),
                (
                    "max_weight",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        help_text="Maximum weight in kg",
                    ),
                ),
                (
                    "base_cost",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        help_text="Base shipping cost",
                    ),
                ),
                (
                    "per_kg_cost",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=10,
                        help_text="Cost per kg over base",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(default=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "zone",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rates",
                        to="shipping.shippingzone",
                    ),
                ),
            ],
            options={
                "db_table": "shipping_rates",
                "indexes": [
                    models.Index(
                        fields=["zone", "min_weight", "max_weight"],
                        name="shipping_rates_zone_weight_idx",
                    ),
                ],
            },
        ),
    ]

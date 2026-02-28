"""Add ShippingZone and ShippingRate models."""

from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("shipping", "0001_initial"),
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
                ("is_active", models.BooleanField(default=True)),
                ("priority", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shipping_zones",
                        to="stores.store",
                    ),
                ),
            ],
            options={
                "verbose_name": "Shipping Zone",
                "verbose_name_plural": "Shipping Zones",
                "db_table": "shipping_zone",
                "ordering": ["-priority", "name"],
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
                ("name", models.CharField(max_length=100)),
                (
                    "rate_type",
                    models.CharField(
                        choices=[
                            ("flat", "Flat Rate"),
                            ("weight", "Weight-Based (per kg)"),
                        ],
                        default="flat",
                        max_length=20,
                    ),
                ),
                (
                    "base_rate",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "min_weight",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "max_weight",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=10,
                        null=True,
                    ),
                ),
                (
                    "free_shipping_threshold",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=10,
                        null=True,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("priority", models.IntegerField(default=0)),
                (
                    "estimated_days",
                    models.IntegerField(blank=True, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "zone",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shipping_rates",
                        to="shipping.shippingzone",
                    ),
                ),
            ],
            options={
                "verbose_name": "Shipping Rate",
                "verbose_name_plural": "Shipping Rates",
                "db_table": "shipping_rate",
                "ordering": ["-priority", "min_weight"],
            },
        ),
        migrations.AddConstraint(
            model_name="shippingzone",
            constraint=models.UniqueConstraint(
                fields=["store", "name"],
                name="unique_zone_per_store",
            ),
        ),
        migrations.AddIndex(
            model_name="shippingzone",
            index=models.Index(fields=["store", "is_active"], name="shipping_zone_store_active_idx"),
        ),
        migrations.AddIndex(
            model_name="shippingzone",
            index=models.Index(fields=["priority"], name="shipping_zone_priority_idx"),
        ),
        migrations.AddIndex(
            model_name="shippingrate",
            index=models.Index(fields=["zone", "is_active"], name="shipping_rate_zone_active_idx"),
        ),
        migrations.AddIndex(
            model_name="shippingrate",
            index=models.Index(fields=["rate_type", "priority"], name="shipping_rate_type_priority_idx"),
        ),
    ]

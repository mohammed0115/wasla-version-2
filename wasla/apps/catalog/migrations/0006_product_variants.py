# Generated manually for product variants + option groups

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_inventory_low_stock_threshold_and_stockmovement"),
        ("stores", "0003_store_tenant_relation"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductOptionGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("is_required", models.BooleanField(default=False)),
                ("position", models.PositiveIntegerField(default=0)),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="product_option_groups",
                        to="stores.store",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["store", "position"], name="catalog_optgrp_store_position_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ProductOption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("value", models.CharField(max_length=120)),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="options",
                        to="catalog.productoptiongroup",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ProductVariant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_id", models.IntegerField(db_index=True, default=1)),
                ("sku", models.CharField(max_length=64)),
                ("price_override", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("stock_quantity", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="variants",
                        to="catalog.product",
                    ),
                ),
                (
                    "options",
                    models.ManyToManyField(blank=True, related_name="variants", to="catalog.productoption"),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["product", "is_active"], name="catalog_variant_product_active_idx"),
                    models.Index(fields=["store_id", "product"], name="catalog_variant_store_product_idx"),
                ],
            },
        ),
        migrations.AddField(
            model_name="stockmovement",
            name="variant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="stock_movements",
                to="catalog.productvariant",
            ),
        ),
        migrations.AddConstraint(
            model_name="productoptiongroup",
            constraint=models.UniqueConstraint(fields=("store", "name"), name="uq_product_option_group_store_name"),
        ),
        migrations.AddConstraint(
            model_name="productoption",
            constraint=models.UniqueConstraint(fields=("group", "value"), name="uq_product_option_group_value"),
        ),
        migrations.AddConstraint(
            model_name="productvariant",
            constraint=models.UniqueConstraint(fields=("store_id", "sku"), name="uq_product_variant_store_sku"),
        ),
    ]

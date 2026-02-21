# Generated manually for Phase 3 (inventory + purchases)

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_product_descriptions"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventory",
            name="low_stock_threshold",
            field=models.PositiveIntegerField(default=5),
        ),
        migrations.CreateModel(
            name="StockMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_id", models.IntegerField(db_index=True, default=1)),
                (
                    "movement_type",
                    models.CharField(
                        choices=[("IN", "In"), ("OUT", "Out"), ("ADJUST", "Adjustment")],
                        max_length=10,
                    ),
                ),
                ("quantity", models.PositiveIntegerField()),
                ("reason", models.CharField(blank=True, default="", max_length=255)),
                ("order_id", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("purchase_order_id", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stock_movements",
                        to="catalog.product",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["store_id", "created_at"]),
                    models.Index(fields=["store_id", "product"]),
                ]
            },
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0009_product_weight"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["store_id", "is_active", "visibility"], name="catalog_prod_store_vis"),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["store_id", "price"], name="catalog_prod_store_price"),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["store_id", "name"], name="catalog_prod_store_name"),
        ),
    ]

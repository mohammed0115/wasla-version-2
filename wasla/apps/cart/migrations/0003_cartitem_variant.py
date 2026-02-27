# Generated manually for cart variant support

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_product_variants"),
        ("cart", "0002_rename_cart_cart_store_i_9c64b3_idx_cart_cart_store_i_de1071_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="cartitem",
            name="variant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="catalog.productvariant",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="cartitem",
            name="uq_cart_item_cart_product",
        ),
        migrations.AddConstraint(
            model_name="cartitem",
            constraint=models.UniqueConstraint(
                fields=("cart", "product", "variant"),
                name="uq_cart_item_cart_product_variant",
            ),
        ),
    ]

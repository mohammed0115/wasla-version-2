# Generated manually for cart variant support

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_product_variants"),
        ("cart", "0003_cart_abandoned_tracking"),
    ]

    operations = [
        migrations.AddField(
            model_name="cartitem",
            name="variant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="catalog.productvariant",
            ),
        ),
    ]

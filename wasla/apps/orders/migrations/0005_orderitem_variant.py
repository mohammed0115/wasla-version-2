# Generated manually for order item variant support

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_product_variants"),
        ("orders", "0004_order_tenant_id_orderitem_tenant_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="variant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="catalog.productvariant",
            ),
        ),
    ]

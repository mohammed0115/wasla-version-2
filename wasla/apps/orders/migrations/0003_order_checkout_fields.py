from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0002_order_store_id_alter_order_status_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="payment_status",
            field=models.CharField(default="pending", max_length=20),
        ),
        migrations.AddField(
            model_name="order",
            name="currency",
            field=models.CharField(default="SAR", max_length=10),
        ),
        migrations.AddField(
            model_name="order",
            name="customer_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="order",
            name="customer_email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="order",
            name="customer_phone",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="order",
            name="shipping_address_json",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="order",
            name="shipping_method_code",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]

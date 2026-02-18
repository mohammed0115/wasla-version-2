from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0003_product_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="description_ar",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="product",
            name="description_en",
            field=models.TextField(blank=True, default=""),
        ),
    ]

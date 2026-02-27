from django.db import migrations, models


def seed_product_visibility(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    Product.objects.filter(is_active=True).update(visibility="enabled")
    Product.objects.filter(is_active=False).update(visibility="disabled")


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0007_product_images"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="visibility",
            field=models.CharField(
                choices=[("enabled", "Enabled"), ("disabled", "Disabled"), ("hidden", "Hidden")],
                default="enabled",
                max_length=20,
            ),
        ),
        migrations.RunPython(seed_product_visibility, migrations.RunPython.noop),
    ]

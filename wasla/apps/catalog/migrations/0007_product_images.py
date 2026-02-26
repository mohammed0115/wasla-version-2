# Generated manually for product multi-image support

from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q

import apps.catalog.models


def backfill_product_primary_images(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    ProductImage = apps.get_model("catalog", "ProductImage")

    for product in Product.objects.exclude(image="").iterator():
        has_any = ProductImage.objects.filter(product_id=product.id).exists()
        if has_any:
            if not ProductImage.objects.filter(product_id=product.id, is_primary=True).exists():
                first = ProductImage.objects.filter(product_id=product.id).order_by("position", "id").first()
                if first:
                    ProductImage.objects.filter(id=first.id).update(is_primary=True)
            continue

        ProductImage.objects.create(
            product_id=product.id,
            image=product.image,
            alt_text=product.name,
            position=0,
            is_primary=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_product_variants"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to=apps.catalog.models.product_gallery_upload_to)),
                ("alt_text", models.CharField(blank=True, default="", max_length=255)),
                ("position", models.PositiveIntegerField(default=0)),
                ("is_primary", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="catalog.product",
                    ),
                ),
            ],
            options={
                "ordering": ["position", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="productimage",
            index=models.Index(fields=["product", "position"], name="catalog_pim_product_position_idx"),
        ),
        migrations.AddConstraint(
            model_name="productimage",
            constraint=models.UniqueConstraint(
                fields=("product",),
                condition=Q(("is_primary", True)),
                name="uq_productimage_single_primary",
            ),
        ),
        migrations.RunPython(backfill_product_primary_images, migrations.RunPython.noop),
    ]

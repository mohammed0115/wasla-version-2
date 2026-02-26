# Generated manually for AR module

import django.core.validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models

import apps.ar.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("catalog", "0007_product_images"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductARAsset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_id", models.IntegerField(db_index=True)),
                (
                    "glb_file",
                    models.FileField(
                        upload_to=apps.ar.models.ar_glb_upload_to,
                        validators=[django.core.validators.FileExtensionValidator(allowed_extensions=["glb"])],
                    ),
                ),
                ("texture_image", models.ImageField(blank=True, null=True, upload_to=apps.ar.models.ar_texture_upload_to)),
                ("is_active", models.BooleanField(default=True)),
                ("metadata_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ar_asset",
                        to="catalog.product",
                    ),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["store_id", "is_active"], name="ar_productar_store_i_4566d4_idx")],
            },
        ),
        migrations.CreateModel(
            name="ARSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_id", models.IntegerField(db_index=True)),
                ("tenant_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("session_id", models.UUIDField(db_index=True, default=uuid.uuid4, unique=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, default="", max_length=255)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("metadata_json", models.JSONField(blank=True, default=dict)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ar_sessions",
                        to="catalog.product",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ar_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["store_id", "started_at"], name="ar_arsessio_store_i_6b06fd_idx"),
                    models.Index(fields=["tenant_id", "started_at"], name="ar_arsessio_tenant__f793dd_idx"),
                    models.Index(fields=["product", "started_at"], name="ar_arsessio_product_1a83af_idx"),
                ],
            },
        ),
    ]

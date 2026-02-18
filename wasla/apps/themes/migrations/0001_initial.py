from django.db import migrations, models
import apps.themes.models
from apps import themes


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Theme",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True)),
                ("name_key", models.CharField(max_length=100)),
                ("preview_image_path", models.CharField(blank=True, default="", max_length=255)),
                ("is_active", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="StoreBranding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_id", models.IntegerField(db_index=True)),
                ("theme_code", models.CharField(blank=True, default="", max_length=50)),
                ("logo_path", models.ImageField(blank=True, null=True, upload_to=apps.themes.models.branding_logo_upload_to)),
                ("primary_color", models.CharField(blank=True, default="", max_length=7)),
                ("secondary_color", models.CharField(blank=True, default="", max_length=7)),
                ("accent_color", models.CharField(blank=True, default="", max_length=7)),
                ("font_family", models.CharField(blank=True, default="", max_length=80)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name="storebranding",
            constraint=models.UniqueConstraint(fields=("store_id",), name="uq_store_branding_store"),
        ),
        migrations.AddIndex(
            model_name="storebranding",
            index=models.Index(fields=["store_id"], name="themes_stor_store_i_7e4c93_idx"),
        ),
    ]

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIRequestLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_id", models.IntegerField(db_index=True)),
                (
                    "feature",
                    models.CharField(
                        choices=[("DESCRIPTION", "Description"), ("CATEGORY", "Category"), ("SEARCH", "Search")],
                        max_length=20,
                    ),
                ),
                ("provider", models.CharField(default="", max_length=50)),
                ("latency_ms", models.IntegerField(default=0)),
                ("token_count", models.IntegerField(blank=True, null=True)),
                ("cost_estimate", models.DecimalField(decimal_places=6, default=0, max_digits=12)),
                (
                    "status",
                    models.CharField(
                        choices=[("SUCCESS", "Success"), ("FAILED", "Failed")],
                        default="SUCCESS",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="AIProductEmbedding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_id", models.IntegerField(db_index=True)),
                ("provider", models.CharField(default="", max_length=50)),
                ("vector", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_embedding",
                        to="catalog.product",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="airequestlog",
            index=models.Index(fields=["store_id", "created_at"], name="ai_aireques_store_i_36f4cc_idx"),
        ),
        migrations.AddIndex(
            model_name="airequestlog",
            index=models.Index(fields=["feature", "created_at"], name="ai_aireques_feature_2c5f21_idx"),
        ),
        migrations.AddIndex(
            model_name="aiproductembedding",
            index=models.Index(fields=["store_id", "created_at"], name="ai_aiprodu_store_i_0fd5e0_idx"),
        ),
    ]

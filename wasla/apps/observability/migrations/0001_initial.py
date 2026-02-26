from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PerformanceBenchmarkReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("profile", models.CharField(db_index=True, default="default", max_length=64)),
                ("host", models.CharField(blank=True, default="", max_length=255)),
                ("runs_per_endpoint", models.PositiveIntegerField(default=1)),
                ("slow_threshold_ms", models.FloatField(default=500.0)),
                ("summary", models.JSONField(blank=True, default=dict)),
                ("report", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name="RequestPerformanceLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("request_id", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("store_id", models.IntegerField(db_index=True)),
                ("endpoint", models.CharField(db_index=True, max_length=255)),
                ("method", models.CharField(max_length=10)),
                ("status_code", models.PositiveIntegerField()),
                ("response_time_ms", models.FloatField()),
                ("db_query_count", models.PositiveIntegerField(default=0)),
                ("cache_hit", models.BooleanField(default=False)),
                ("is_slow", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["store_id", "created_at"], name="apps_observ_store_i_0bc92e_idx"),
                    models.Index(fields=["endpoint", "created_at"], name="apps_observ_endpoin_39cc07_idx"),
                    models.Index(fields=["store_id", "endpoint", "created_at"], name="apps_observ_store_i_35772a_idx"),
                ],
            },
        ),
    ]

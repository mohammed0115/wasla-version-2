from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("observability", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PerformanceLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("path", models.CharField(db_index=True, max_length=255)),
                ("method", models.CharField(max_length=10)),
                ("store", models.IntegerField(db_index=True)),
                ("duration_ms", models.FloatField(db_index=True)),
                ("query_count", models.PositiveIntegerField(default=0)),
                ("status_code", models.PositiveIntegerField()),
                ("request_id", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["store", "created_at"], name="apps_observ_store_2bfade_idx"),
                    models.Index(fields=["path", "created_at"], name="apps_observ_path_33f007_idx"),
                    models.Index(fields=["duration_ms", "created_at"], name="apps_observ_duratio_455628_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PerformanceReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("run_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("summary_json", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(db_index=True, default="ok", max_length=20)),
            ],
        ),
    ]

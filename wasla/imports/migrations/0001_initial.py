from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ImportJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_id", models.IntegerField(db_index=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("CREATED", "Created"),
                            ("VALIDATING", "Validating"),
                            ("IMPORTING", "Importing"),
                            ("COMPLETED", "Completed"),
                            ("FAILED", "Failed"),
                        ],
                        default="CREATED",
                        max_length=20,
                    ),
                ),
                ("source_type", models.CharField(choices=[("CSV", "CSV")], default="CSV", max_length=20)),
                ("original_file_path", models.CharField(blank=True, default="", max_length=500)),
                ("total_rows", models.PositiveIntegerField(default=0)),
                ("success_rows", models.PositiveIntegerField(default=0)),
                ("failed_rows", models.PositiveIntegerField(default=0)),
                ("errors_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="import_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ImportRowError",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("row_number", models.PositiveIntegerField()),
                ("field", models.CharField(blank=True, default="", max_length=100)),
                ("message_key", models.CharField(max_length=200)),
                ("raw_value", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "import_job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="row_errors", to="imports.importjob"
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="importjob",
            index=models.Index(fields=["store_id", "created_at"], name="imports_impo_store_c0d915_idx"),
        ),
        migrations.AddIndex(
            model_name="importjob",
            index=models.Index(fields=["store_id", "status"], name="imports_impo_store_3b8f23_idx"),
        ),
        migrations.AddIndex(
            model_name="importrowerror",
            index=models.Index(fields=["import_job", "row_number"], name="imports_impo_import_4e2b7f_idx"),
        ),
    ]

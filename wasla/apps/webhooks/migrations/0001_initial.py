from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="WebhookEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider_code", models.CharField(max_length=50)),
                ("event_id", models.CharField(max_length=120)),
                ("idempotency_key", models.CharField(max_length=180, unique=True)),
                ("payload_json", models.JSONField(blank=True, default=dict)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("processing_status", models.CharField(choices=[("PENDING", "Pending"), ("PROCESSED", "Processed"), ("FAILED", "Failed")], default="PENDING", max_length=20)),
            ],
        ),
        migrations.AddIndex(
            model_name="webhookevent",
            index=models.Index(fields=["provider_code", "event_id"], name="webhooks_web_provid_0a8e96_idx"),
        ),
        migrations.AddIndex(
            model_name="webhookevent",
            index=models.Index(fields=["processing_status", "received_at"], name="webhooks_web_process_90b774_idx"),
        ),
    ]

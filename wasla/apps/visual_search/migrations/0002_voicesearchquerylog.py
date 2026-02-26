# Generated manually for voice search logging

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("visual_search", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="VoiceSearchQueryLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_id", models.IntegerField(db_index=True)),
                ("tenant_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("user_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("transcript", models.TextField()),
                ("stt_provider", models.CharField(max_length=40)),
                ("language", models.CharField(blank=True, default="", max_length=16)),
                ("audio_content_type", models.CharField(blank=True, default="", max_length=80)),
                ("result_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["store_id", "created_at"], name="vs_voice_store_created_idx"),
                    models.Index(fields=["tenant_id", "created_at"], name="vs_voice_tenant_created_idx"),
                ],
            },
        ),
    ]

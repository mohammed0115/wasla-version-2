from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("webhooks", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="webhookevent",
            name="payload_raw",
            field=models.TextField(blank=True, default=""),
        ),
    ]

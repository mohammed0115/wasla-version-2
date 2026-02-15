from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="aiproductembedding",
            name="attributes",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

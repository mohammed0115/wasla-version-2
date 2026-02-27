from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("domains", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="domainhealth",
            name="last_error",
            field=models.TextField(blank=True, null=True),
        ),
    ]

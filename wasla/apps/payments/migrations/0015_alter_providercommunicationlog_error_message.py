from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0014_paymentrisk_model_backfill"),
    ]

    operations = [
        migrations.AlterField(
            model_name="providercommunicationlog",
            name="error_message",
            field=models.TextField(blank=True, null=True, default=None),
        ),
    ]

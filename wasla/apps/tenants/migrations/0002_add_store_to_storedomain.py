from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("stores", "0001_initial"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="storedomain",
            name="store",
            field=models.ForeignKey(
                blank=True,
                help_text="Resolved store for this host mapping.",
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="domains",
                to="stores.store",
            ),
        ),
        migrations.AlterField(
            model_name="storedomain",
            name="is_primary",
            field=models.BooleanField(default=True),
        ),
    ]

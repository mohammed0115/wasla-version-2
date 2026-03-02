from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("stores", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="store",
            name="is_platform_default",
            field=models.BooleanField(
                default=False,
                help_text="Marks the platform landing store for the root domain.",
            ),
        ),
        migrations.AddConstraint(
            model_name="store",
            constraint=models.UniqueConstraint(
                fields=("is_platform_default",),
                condition=models.Q(("is_platform_default", True)),
                name="stores_single_platform_default",
            ),
        ),
    ]

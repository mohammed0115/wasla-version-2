from django.db import migrations


def create_default_global_email_settings(apps, schema_editor):
    GlobalEmailSettings = apps.get_model("emails", "GlobalEmailSettings")
    if GlobalEmailSettings.objects.exists():
        return
    GlobalEmailSettings.objects.create(enabled=False)


class Migration(migrations.Migration):
    dependencies = [
        ("emails", "0002_globalemailsettings_globalemailsettingsauditlog"),
    ]

    operations = [
        migrations.RunPython(
            create_default_global_email_settings,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

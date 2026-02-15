from django.db import migrations


def seed_themes(apps, schema_editor):
    Theme = apps.get_model("themes", "Theme")
    defaults = [
        {"code": "classic", "name_key": "theme.classic", "preview_image_path": "", "is_active": True},
        {"code": "modern", "name_key": "theme.modern", "preview_image_path": "", "is_active": True},
        {"code": "minimal", "name_key": "theme.minimal", "preview_image_path": "", "is_active": True},
    ]
    for item in defaults:
        Theme.objects.get_or_create(code=item["code"], defaults=item)


class Migration(migrations.Migration):
    dependencies = [
        ("themes", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_themes, migrations.RunPython.noop),
    ]

from django.db import migrations


def create_default_tenant(apps, schema_editor):
    Tenant = apps.get_model("tenants", "Tenant")
    if Tenant.objects.exists():
        return
    Tenant.objects.create(slug="default", name="Default Store", is_active=True)


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_tenant, migrations.RunPython.noop),
    ]


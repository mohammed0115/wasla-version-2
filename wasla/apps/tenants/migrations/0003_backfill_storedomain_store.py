from django.db import migrations


def _backfill_store(apps, _schema_editor):
    StoreDomain = apps.get_model("tenants", "StoreDomain")
    Store = apps.get_model("stores", "Store")

    for domain in StoreDomain.objects.filter(store__isnull=True).iterator():
        store = Store.objects.filter(tenant_id=domain.tenant_id).order_by("id").first()
        if store:
            StoreDomain.objects.filter(id=domain.id).update(store_id=store.id)


def _noop_reverse(apps, _schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0002_add_store_to_storedomain"),
        ("stores", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(_backfill_store, _noop_reverse),
    ]

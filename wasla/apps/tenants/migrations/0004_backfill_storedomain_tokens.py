from django.db import migrations


def backfill_verification_tokens(apps, schema_editor):
    StoreDomain = apps.get_model("tenants", "StoreDomain")
    import secrets

    qs = StoreDomain.objects.filter(verification_token="")
    for domain in qs.iterator():
        token = secrets.token_urlsafe(32)
        while StoreDomain.objects.filter(verification_token=token).exists():
            token = secrets.token_urlsafe(32)
        StoreDomain.objects.filter(id=domain.id).update(verification_token=token)


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0003_backfill_storedomain_store"),
    ]

    operations = [
        migrations.RunPython(backfill_verification_tokens, migrations.RunPython.noop),
    ]

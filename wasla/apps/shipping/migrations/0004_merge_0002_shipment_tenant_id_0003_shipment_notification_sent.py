from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("shipping", "0002_shipment_tenant_id"),
        ("shipping", "0003_shipment_notification_sent"),
    ]

    operations = []

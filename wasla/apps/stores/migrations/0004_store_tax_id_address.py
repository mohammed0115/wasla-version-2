from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("stores", "0003_store_tenant_relation"),
    ]

    operations = [
        migrations.AddField(
            model_name="store",
            name="tax_id",
            field=models.CharField(
                max_length=20,
                blank=True,
                default="",
                help_text="VAT ID for invoices (ZATCA)",
            ),
        ),
        migrations.AddField(
            model_name="store",
            name="address",
            field=models.CharField(
                max_length=255,
                blank=True,
                default="",
                help_text="Store address for invoices",
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0010_store_domain"),
    ]

    operations = [
        migrations.AlterField(
            model_name="storedomain",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING_VERIFICATION", "Pending Verification"),
                    ("VERIFIED", "Verified"),
                    ("SSL_PENDING", "SSL Pending"),
                    ("SSL_ACTIVE", "SSL Active"),
                    ("PENDING", "Pending"),
                    ("VERIFYING", "Verifying"),
                    ("ACTIVE", "Active"),
                    ("FAILED", "Failed"),
                    ("DISABLED", "Disabled"),
                ],
                default="PENDING_VERIFICATION",
                max_length=30,
            ),
        ),
    ]

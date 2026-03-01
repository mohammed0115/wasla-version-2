from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_totp_secret"),
    ]

    operations = [
        migrations.AlterField(
            model_name="totpsecret",
            name="secret",
            field=models.TextField(help_text="Base32-encoded TOTP secret (encrypted)"),
        ),
    ]

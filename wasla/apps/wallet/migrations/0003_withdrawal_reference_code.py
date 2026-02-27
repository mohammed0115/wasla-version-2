# Generated migration for adding reference_code to WithdrawalRequest

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0002_operational_accounting'),
    ]

    operations = [
        migrations.AddField(
            model_name='withdrawalrequest',
            name='reference_code',
            field=models.CharField(db_index=True, default='', max_length=64, unique=True),
            preserve_default=False,
        ),
        migrations.AddIndex(
            model_name='withdrawalrequest',
            index=models.Index(fields=['reference_code'], name='wallet_withdrawal_ref_idx'),
        ),
    ]

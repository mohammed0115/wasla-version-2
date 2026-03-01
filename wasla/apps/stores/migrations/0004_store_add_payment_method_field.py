# Generated migration for Store.payment_method field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0003_store_tenant_relation'),
    ]

    operations = [
        migrations.AddField(
            model_name='store',
            name='payment_method',
            field=models.CharField(
                blank=True,
                choices=[
                    ('stripe', 'Stripe'),
                    ('tap', 'Tap (Arab Payments)'),
                    ('manual', 'Manual Bank Transfer'),
                ],
                help_text='Payment method selected during onboarding',
                max_length=20,
                null=True,
            ),
        ),
    ]

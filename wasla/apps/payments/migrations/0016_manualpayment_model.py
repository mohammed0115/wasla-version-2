# Generated migration for ManualPayment model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0003_store_tenant_relation'),
        ('payments', '0015_alter_providercommunicationlog_error_message'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ManualPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, help_text='Amount due for plan', max_digits=12)),
                ('currency', models.CharField(default='SAR', help_text='Payment currency', max_length=3)),
                ('reference', models.CharField(blank=True, default='', help_text='Bank transfer reference/receipt number', max_length=255)),
                ('receipt_file', models.FileField(blank=True, help_text='Receipt image/document (optional)', null=True, upload_to='manual_payments/%Y/%m/%d/')),
                ('notes_user', models.TextField(blank=True, default='', help_text='Customer notes about payment')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending Review'),
                        ('approved', 'Approved'),
                        ('rejected', 'Rejected'),
                    ],
                    default='pending',
                    help_text='Approval status',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reviewed_at', models.DateTimeField(blank=True, help_text='When admin reviewed this payment', null=True)),
                ('notes_admin', models.TextField(blank=True, default='', help_text='Admin notes on approval/rejection')),
                ('plan', models.ForeignKey(help_text='Plan being purchased', on_delete=django.db.models.deletion.PROTECT, related_name='manual_payments', to='subscriptions.subscriptionplan')),
                ('reviewed_by', models.ForeignKey(blank=True, help_text='Admin who approved/rejected', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_manual_payments', to=settings.AUTH_USER_MODEL)),
                ('store', models.ForeignKey(help_text='Store paying via manual transfer', on_delete=django.db.models.deletion.CASCADE, related_name='manual_payments', to='stores.store')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='manualpayment',
            index=models.Index(fields=['store', 'status'], name='payments_ma_store__3d5a8c_idx'),
        ),
        migrations.AddIndex(
            model_name='manualpayment',
            index=models.Index(fields=['status', 'created_at'], name='payments_ma_status_7e2b4f_idx'),
        ),
    ]

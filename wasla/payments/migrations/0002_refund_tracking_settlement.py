"""
Database Migration: Add RefundRecord and enhance PaymentProviderSettings
Generated: 2026-02-17

This migration:
1. Creates the RefundRecord model for refund tracking with audit trail
2. Adds fee tracking fields to PaymentProviderSettings
"""

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),  # Adjust to your actual previous migration
        ('orders', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Create RefundRecord model
        migrations.CreateModel(
            name='RefundRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('approved', 'Approved'),
                        ('rejected', 'Rejected'),
                        ('failed', 'Failed'),
                        ('completed', 'Completed'),
                    ],
                    default='pending',
                    max_length=20
                )),
                ('provider_reference', models.CharField(blank=True, max_length=255, null=True)),
                ('raw_response', models.JSONField(default=dict, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('payment_intent', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='refunds',
                    to='payments.paymentintent'
                )),
                ('requested_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='refund_requests',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Refund Record',
                'verbose_name_plural': 'Refund Records',
                'db_table': 'payments_refundrecord',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['payment_intent', 'status'], name='refund_payment_status_idx'),
                    models.Index(fields=['created_at'], name='refund_created_idx'),
                ],
            },
        ),

        # Add fields to PaymentProviderSettings
        migrations.AddField(
            model_name='paymentprovidersettings',
            name='transaction_fee_percent',
            field=models.DecimalField(
                decimal_places=2,
                default=2.5,
                help_text='Percentage fee charged by provider (e.g., 2.5% for Tap)',
                max_digits=5,
                verbose_name='Transaction Fee %'
            ),
        ),

        migrations.AddField(
            model_name='paymentprovidersettings',
            name='wasla_commission_percent',
            field=models.DecimalField(
                decimal_places=2,
                default=3.0,
                help_text='Percentage commission kept by WASLA platform',
                max_digits=5,
                verbose_name='WASLA Commission %'
            ),
        ),

        migrations.AddField(
            model_name='paymentprovidersettings',
            name='is_sandbox_mode',
            field=models.BooleanField(
                default=False,
                help_text='Enable sandbox/test mode for this provider',
                verbose_name='Sandbox Mode'
            ),
        ),

        # Add indexes for better query performance
        migrations.AddIndex(
            model_name='refundrecord',
            index=models.Index(fields=['status'], name='refund_status_idx'),
        ),

        migrations.AddIndex(
            model_name='refundrecord',
            index=models.Index(fields=['requested_by'], name='refund_requested_by_idx'),
        ),
    ]

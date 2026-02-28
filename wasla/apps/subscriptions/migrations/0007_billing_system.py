# Generated migration for automated recurring billing system

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0006_add_payment_methods_to_plan_features'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # Create BillingPlan (extends existing SubscriptionPlan)
        migrations.CreateModel(
            name='BillingPlan',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('price', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('currency', models.CharField(default='SAR', max_length=3)),
                ('billing_cycle', models.CharField(choices=[('monthly', 'Monthly'), ('yearly', 'Yearly'), ('quarterly', 'Quarterly')], default='monthly', max_length=20)),
                ('features', models.JSONField(blank=True, default=list)),
                ('max_products', models.PositiveIntegerField(blank=True, help_text='Max products allowed. Null = unlimited.', null=True)),
                ('max_orders_monthly', models.PositiveIntegerField(blank=True, help_text='Max orders per month. Null = unlimited.', null=True)),
                ('max_staff_users', models.PositiveIntegerField(blank=True, help_text='Max staff users. Null = unlimited.', null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'subscriptions_subscription_plan',
            },
        ),

        # Create Subscription (full-featured subscription with state machine)
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('currency', models.CharField(default='SAR', max_length=3)),
                ('billing_cycle_anchor', models.DateField(help_text='Day of month when billing cycle renews (1-28)')),
                ('next_billing_date', models.DateField()),
                ('state', models.CharField(choices=[('active', 'Active'), ('past_due', 'Past Due'), ('grace', 'Grace Period'), ('suspended', 'Suspended'), ('cancelled', 'Cancelled')], default='active', max_length=20)),
                ('grace_until', models.DateTimeField(blank=True, help_text='Extends deadline for payment if set', null=True)),
                ('suspended_at', models.DateTimeField(blank=True, null=True)),
                ('suspension_reason', models.CharField(blank=True, max_length=255)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('cancellation_reason', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='subscriptions', to='subscriptions.billingplan')),
                ('tenant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='subscription', to='tenants.tenant')),
            ],
            options={
                'db_table': 'subscriptions_subscription',
            },
        ),

        # Create PaymentMethod
        migrations.CreateModel(
            name='PaymentMethod',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('method_type', models.CharField(choices=[('card', 'Credit/Debit Card'), ('bank', 'Bank Account'), ('wallet', 'Digital Wallet'), ('other', 'Other')], default='card', max_length=20)),
                ('provider_customer_id', models.CharField(help_text='Customer ID from payment provider', max_length=255)),
                ('provider_payment_method_id', models.CharField(help_text='Payment method ID from payment provider', max_length=255)),
                ('display_name', models.CharField(blank=True, help_text='e.g., Last 4 digits, bank name', max_length=255)),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive'), ('expired', 'Expired'), ('invalid', 'Invalid')], default='active', max_length=20)),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('subscription', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='payment_method', to='subscriptions.subscription')),
            ],
            options={
                'db_table': 'subscriptions_payment_method',
            },
        ),

        # Create SubscriptionItem (for usage-based billing)
        migrations.CreateModel(
            name='SubscriptionItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('billing_type', models.CharField(choices=[('fixed', 'Fixed'), ('usage', 'Usage-based'), ('metered', 'Metered')], default='fixed', max_length=20)),
                ('price', models.DecimalField(decimal_places=2, max_digits=12)),
                ('currency', models.CharField(default='SAR', max_length=3)),
                ('current_usage', models.PositiveIntegerField(default=0)),
                ('usage_limit', models.PositiveIntegerField(blank=True, help_text='Max usage per billing cycle', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='subscriptions.subscription')),
            ],
            options={
                'db_table': 'subscriptions_subscription_item',
            },
        ),

        # Create BillingCycle
        migrations.CreateModel(
            name='BillingCycle',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('period_start', models.DateField()),
                ('period_end', models.DateField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('billed', 'Billed'), ('partial', 'Partial Payment'), ('paid', 'Paid'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('subtotal', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('discount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('tax', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('total', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('proration_total', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('proration_reason', models.CharField(blank=True, max_length=255)),
                ('invoice_date', models.DateField(blank=True, null=True)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='billing_cycles', to='subscriptions.subscription')),
            ],
            options={
                'db_table': 'subscriptions_billing_cycle',
                'ordering': ['-period_end'],
            },
        ),

        # Create Invoice
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('number', models.CharField(db_index=True, max_length=50, unique=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('issued', 'Issued'), ('overdue', 'Overdue'), ('partial', 'Partial Payment'), ('paid', 'Paid'), ('void', 'Void')], default='draft', max_length=20)),
                ('subtotal', models.DecimalField(decimal_places=2, max_digits=12)),
                ('tax', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('discount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('total', models.DecimalField(decimal_places=2, max_digits=12)),
                ('amount_paid', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('amount_due', models.DecimalField(decimal_places=2, max_digits=12)),
                ('issued_date', models.DateField(auto_now_add=True)),
                ('due_date', models.DateField()),
                ('paid_date', models.DateField(blank=True, null=True)),
                ('idempotency_key', models.CharField(db_index=True, help_text='Ensures invoice is only created once', max_length=255, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('billing_cycle', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='invoice', to='subscriptions.billingcycle')),
                ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invoices', to='subscriptions.subscription')),
            ],
            options={
                'db_table': 'subscriptions_invoice',
                'ordering': ['-issued_date'],
            },
        ),

        # Create DunningAttempt
        migrations.CreateModel(
            name='DunningAttempt',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('attempt_number', models.PositiveIntegerField(default=1)),
                ('strategy', models.CharField(choices=[('immediate', 'Immediate Retry'), ('incremental', 'Incremental Retry'), ('exponential', 'Exponential Backoff')], default='exponential', max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('success', 'Success'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('scheduled_for', models.DateTimeField()),
                ('attempted_at', models.DateTimeField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True)),
                ('error_code', models.CharField(blank=True, max_length=50)),
                ('next_retry_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dunning_attempts', to='subscriptions.invoice')),
                ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dunning_attempts', to='subscriptions.subscription')),
            ],
            options={
                'db_table': 'subscriptions_dunning_attempt',
                'ordering': ['-created_at'],
            },
        ),

        # Create PaymentEvent
        migrations.CreateModel(
            name='PaymentEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_type', models.CharField(choices=[('payment.succeeded', 'Payment Succeeded'), ('payment.failed', 'Payment Failed'), ('invoice.paid', 'Invoice Paid'), ('invoice.payment_failed', 'Invoice Payment Failed'), ('customer.subscription.updated', 'Subscription Updated')], max_length=50)),
                ('provider_event_id', models.CharField(db_index=True, help_text='External ID from payment provider (idempotency key)', max_length=255, unique=True)),
                ('payload', models.JSONField(help_text='Full webhook payload from provider')),
                ('status', models.CharField(choices=[('received', 'Received'), ('processing', 'Processing'), ('processed', 'Processed'), ('failed', 'Failed')], default='received', max_length=20)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('invoice', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='payment_events', to='subscriptions.invoice')),
                ('subscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='payment_events', to='subscriptions.subscription')),
            ],
            options={
                'db_table': 'subscriptions_payment_event',
                'ordering': ['-created_at'],
            },
        ),

        # Add database indexes
        migrations.AddIndex(
            model_name='subscription',
            index=models.Index(fields=['tenant', 'state'], name='subscriptions_tenant_state_idx'),
        ),
        migrations.AddIndex(
            model_name='subscription',
            index=models.Index(fields=['state', 'next_billing_date'], name='subscriptions_state_billing_idx'),
        ),
        migrations.AddIndex(
            model_name='billingcycle',
            index=models.Index(fields=['subscription', 'period_end'], name='subscriptions_sub_period_idx'),
        ),
        migrations.AddIndex(
            model_name='billingcycle',
            index=models.Index(fields=['status', 'due_date'], name='subscriptions_status_due_idx'),
        ),
        migrations.AddIndex(
            model_name='invoice',
            index=models.Index(fields=['subscription', 'status'], name='subscriptions_inv_sub_status_idx'),
        ),
        migrations.AddIndex(
            model_name='invoice',
            index=models.Index(fields=['status', 'due_date'], name='subscriptions_inv_status_due_idx'),
        ),
        migrations.AddIndex(
            model_name='invoice',
            index=models.Index(fields=['number'], name='subscriptions_inv_number_idx'),
        ),
        migrations.AddIndex(
            model_name='dunningattempt',
            index=models.Index(fields=['invoice', 'status'], name='subscriptions_dun_inv_status_idx'),
        ),
        migrations.AddIndex(
            model_name='dunningattempt',
            index=models.Index(fields=['subscription', 'status'], name='subscriptions_dun_sub_status_idx'),
        ),
        migrations.AddIndex(
            model_name='dunningattempt',
            index=models.Index(fields=['status', 'scheduled_for'], name='subscriptions_dun_status_sched_idx'),
        ),
        migrations.AddIndex(
            model_name='paymentevent',
            index=models.Index(fields=['provider_event_id'], name='subscriptions_evt_provider_id_idx'),
        ),
        migrations.AddIndex(
            model_name='paymentevent',
            index=models.Index(fields=['subscription', 'status'], name='subscriptions_evt_sub_status_idx'),
        ),
        migrations.AddIndex(
            model_name='paymentevent',
            index=models.Index(fields=['status', 'created_at'], name='subscriptions_evt_status_created_idx'),
        ),
    ]

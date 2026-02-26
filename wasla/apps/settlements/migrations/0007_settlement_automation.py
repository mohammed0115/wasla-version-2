# Generated migration for settlement automation models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('settlements', '0005_invoice_invoiceline_and_more'),
        ('stores', '0001_initial'),
    ]

    operations = [
        # SettlementBatch
        migrations.CreateModel(
            name='SettlementBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tenant_id', models.IntegerField(blank=True, db_index=True, null=True)),
                ('batch_reference', models.CharField(db_index=True, help_text='Unique identifier for this batch (e.g., BATCH-2026-02-25-001)', max_length=255)),
                ('idempotency_key', models.CharField(db_index=True, help_text='UUID to ensure idempotent processing', max_length=255, unique=True)),
                ('total_orders', models.PositiveIntegerField(default=0)),
                ('total_amount', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('total_fees', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('total_net', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('status', models.CharField(choices=[('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed'), ('partial', 'Partial')], db_index=True, default='processing', max_length=20)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('failed_reason', models.TextField(blank=True, default='')),
                ('orders_succeeded', models.PositiveIntegerField(default=0)),
                ('orders_failed', models.PositiveIntegerField(default=0)),
                ('duration_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='settlement_batches', to='stores.store')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        
        # SettlementBatchItem
        migrations.CreateModel(
            name='SettlementBatchItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('calculated_fee', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('calculated_net', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('status', models.CharField(choices=[('included', 'Included'), ('processed', 'Processed'), ('failed', 'Failed'), ('skipped', 'Skipped')], default='included', max_length=20)),
                ('error_message', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='settlements.settlementbatch')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='batch_items', to='orders.order')),
            ],
        ),
        
        # SettlementRunLog
        migrations.CreateModel(
            name='SettlementRunLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tenant_id', models.IntegerField(blank=True, db_index=True, null=True)),
                ('task_name', models.CharField(db_index=True, max_length=255)),
                ('task_id', models.CharField(blank=True, max_length=255, null=True, unique=True)),
                ('status', models.CharField(choices=[('started', 'Started'), ('completed', 'Completed'), ('failed', 'Failed')], db_index=True, default='started', max_length=20)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('duration_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('message', models.TextField(blank=True, default='')),
                ('payload_json', models.JSONField(blank=True, default=dict)),
                ('error_trace', models.TextField(blank=True, default='')),
                ('orders_processed', models.PositiveIntegerField(default=0)),
                ('batches_created', models.PositiveIntegerField(default=0)),
                ('total_amount', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('store', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='settlement_run_logs', to='stores.store')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        
        # ReconciliationReport
        migrations.CreateModel(
            name='ReconciliationReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tenant_id', models.IntegerField(blank=True, db_index=True, null=True)),
                ('period_start', models.DateField(db_index=True)),
                ('period_end', models.DateField(db_index=True)),
                ('expected_total', models.DecimalField(decimal_places=2, max_digits=14)),
                ('settled_total', models.DecimalField(decimal_places=2, max_digits=14)),
                ('discrepancy', models.DecimalField(decimal_places=2, max_digits=14)),
                ('discrepancy_percentage', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('unsettled_orders_count', models.PositiveIntegerField(default=0)),
                ('orphaned_items_count', models.PositiveIntegerField(default=0)),
                ('amount_mismatch_count', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('ok', 'OK'), ('warning', 'Warning'), ('error', 'Error')], db_index=True, default='ok', max_length=20)),
                ('findings', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('store', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reconciliation_reports', to='stores.store')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        
        # Add indexes
        migrations.AddIndex(
            model_name='settlementbatch',
            index=models.Index(fields=['store', 'status', 'created_at'], name='settlements_store_status_created_idx'),
        ),
        migrations.AddIndex(
            model_name='settlementbatch',
            index=models.Index(fields=['idempotency_key'], name='settlements_idempotency_key_idx'),
        ),
        migrations.AddIndex(
            model_name='settlementbatch',
            index=models.Index(fields=['status', 'created_at'], name='settlements_status_created_idx'),
        ),
        migrations.AddIndex(
            model_name='settlementbatchitem',
            index=models.Index(fields=['batch', 'status'], name='settlements_batch_status_idx'),
        ),
        migrations.AddIndex(
            model_name='settlementbatchitem',
            index=models.Index(fields=['order'], name='settlements_order_idx'),
        ),
        migrations.AddIndex(
            model_name='settlementrunlog',
            index=models.Index(fields=['task_name', 'created_at'], name='settlements_task_created_idx'),
        ),
        migrations.AddIndex(
            model_name='settlementrunlog',
            index=models.Index(fields=['status', 'created_at'], name='settlements_runlog_status_created_idx'),
        ),
        migrations.AddIndex(
            model_name='settlementrunlog',
            index=models.Index(fields=['store', 'created_at'], name='settlements_store_created_idx'),
        ),
        migrations.AddIndex(
            model_name='reconciliationreport',
            index=models.Index(fields=['store', 'created_at'], name='reconciliation_store_created_idx'),
        ),
        migrations.AddIndex(
            model_name='reconciliationreport',
            index=models.Index(fields=['status', 'created_at'], name='reconciliation_status_created_idx'),
        ),
        
        # Add constraints
        migrations.AddConstraint(
            model_name='settlementbatch',
            constraint=models.UniqueConstraint(fields=['store', 'batch_reference'], name='uq_settlement_batch_reference'),
        ),
        migrations.AddConstraint(
            model_name='settlementbatchitem',
            constraint=models.UniqueConstraint(fields=['batch', 'order'], name='uq_batch_item_unique'),
        ),
        migrations.AddConstraint(
            model_name='reconciliationreport',
            constraint=models.UniqueConstraint(fields=['store', 'period_start', 'period_end'], name='uq_reconciliation_report_period'),
        ),
    ]

"""
Migration: Add production commerce models

Adds:
- StockReservation model
- Invoice and InvoiceLineItem models
- RMA, ReturnItem models
- RefundTransaction model
- Order.shipping_charge field
- Updated Order.status choices with return/refund states
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_order_store_id_alter_order_status_and_more'),
        ('catalog', '0001_initial'),
    ]

    operations = [
        # Add shipping_charge field to Order
        migrations.AddField(
            model_name='order',
            name='shipping_charge',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),

        # Update Order.status choices
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('paid', 'Paid'),
                    ('processing', 'Processing'),
                    ('shipped', 'Shipped'),
                    ('delivered', 'Delivered'),
                    ('completed', 'Completed'),
                    ('returned', 'Returned'),
                    ('partially_refunded', 'Partially Refunded'),
                    ('refunded', 'Refunded'),
                    ('cancelled', 'Cancelled'),
                ],
                default='pending',
                max_length=20,
            ),
        ),

        # StockReservation model
        migrations.CreateModel(
            name='StockReservation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tenant_id', models.IntegerField(db_index=True)),
                ('store_id', models.IntegerField(db_index=True)),
                ('reserved_quantity', models.PositiveIntegerField()),
                ('status', models.CharField(
                    choices=[
                        ('reserved', 'Reserved'),
                        ('confirmed', 'Confirmed'),
                        ('released', 'Released'),
                        ('expired', 'Expired'),
                    ],
                    default='reserved',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('released_at', models.DateTimeField(blank=True, null=True)),
                ('release_reason', models.CharField(blank=True, default='', max_length=255)),
                ('inventory', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reservations', to='catalog.inventory')),
                ('order_item', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='stock_reservation', to='orders.orderitem')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['store_id', 'status'], name='orders_stoc_store_i_123abc_idx'),
                    models.Index(fields=['tenant_id', 'expires_at'], name='orders_stoc_tenant_i_456def_idx'),
                    models.Index(fields=['order_item_id'], name='orders_stoc_order_i_789ghi_idx'),
                ],
            },
        ),

        # Invoice model
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tenant_id', models.IntegerField(db_index=True)),
                ('store_id', models.IntegerField(db_index=True)),
                ('invoice_number', models.CharField(db_index=True, max_length=64, unique=True)),
                ('issue_date', models.DateField(auto_now_add=True)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('subtotal', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('tax_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('tax_rate', models.DecimalField(decimal_places=2, default='15', max_digits=5)),
                ('discount_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('shipping_cost', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('total_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('currency', models.CharField(default='SAR', max_length=10)),
                ('status', models.CharField(
                    choices=[
                        ('draft', 'Draft'),
                        ('issued', 'Issued'),
                        ('paid', 'Paid'),
                        ('cancelled', 'Cancelled'),
                        ('refunded', 'Refunded'),
                    ],
                    default='draft',
                    max_length=20,
                )),
                ('buyer_name', models.CharField(max_length=255)),
                ('buyer_email', models.EmailField(max_length=254)),
                ('buyer_vat_id', models.CharField(blank=True, default='', max_length=64)),
                ('seller_name', models.CharField(max_length=255)),
                ('seller_vat_id', models.CharField(blank=True, default='', max_length=64)),
                ('seller_address', models.TextField(blank=True, default='')),
                ('seller_bank_details', models.JSONField(blank=True, default=dict)),
                ('zatca_qr_code', models.TextField(blank=True, default='')),
                ('zatca_uuid', models.CharField(blank=True, default='', max_length=64)),
                ('zatca_hash', models.CharField(blank=True, default='', max_length=256)),
                ('zatca_signed', models.BooleanField(default=False)),
                ('pdf_file', models.FileField(blank=True, null=True, upload_to='invoices/%Y/%m/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('issued_at', models.DateTimeField(blank=True, null=True)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('order', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='invoice', to='orders.order')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['store_id', '-issue_date'], name='orders_invo_store_i_123abc_idx'),
                    models.Index(fields=['tenant_id', 'status'], name='orders_invo_tenant_i_456def_idx'),
                    models.Index(fields=['buyer_email'], name='orders_invo_buyer_e_789ghi_idx'),
                ],
            },
        ),

        # InvoiceLineItem model
        migrations.CreateModel(
            name='InvoiceLineItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tenant_id', models.IntegerField(db_index=True)),
                ('description', models.CharField(max_length=255)),
                ('sku', models.CharField(blank=True, max_length=100)),
                ('quantity', models.PositiveIntegerField()),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=12)),
                ('line_subtotal', models.DecimalField(decimal_places=2, max_digits=12)),
                ('line_tax', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('line_total', models.DecimalField(decimal_places=2, max_digits=12)),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='line_items', to='orders.invoice')),
                ('order_item', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='orders.orderitem')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['invoice_id'], name='orders_invo_invoice_123abc_idx'),
                ],
            },
        ),

        # RMA model
        migrations.CreateModel(
            name='RMA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tenant_id', models.IntegerField(db_index=True)),
                ('store_id', models.IntegerField(db_index=True)),
                ('rma_number', models.CharField(db_index=True, max_length=64, unique=True)),
                ('reason', models.CharField(
                    choices=[
                        ('defective', 'Defective/Broken'),
                        ('not_as_described', 'Not as Described'),
                        ('changed_mind', 'Changed Mind'),
                        ('damaged_in_shipping', 'Damaged in Shipping'),
                        ('other', 'Other'),
                    ],
                    max_length=32,
                )),
                ('reason_description', models.TextField(blank=True, default='')),
                ('status', models.CharField(
                    choices=[
                        ('requested', 'Requested'),
                        ('approved', 'Approved'),
                        ('rejected', 'Rejected'),
                        ('in_transit', 'In Transit'),
                        ('received', 'Received'),
                        ('inspected', 'Inspected'),
                        ('completed', 'Completed'),
                        ('cancelled', 'Cancelled'),
                    ],
                    default='requested',
                    max_length=20,
                )),
                ('is_exchange', models.BooleanField(default=False)),
                ('return_tracking_number', models.CharField(blank=True, default='', max_length=255)),
                ('return_carrier', models.CharField(blank=True, default='', max_length=64)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('received_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('exchange_product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='catalog.product')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rmas', to='orders.order')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['store_id', 'status'], name='orders_rma_store_i_123abc_idx'),
                    models.Index(fields=['order_id'], name='orders_rma_order_i_456def_idx'),
                ],
            },
        ),

        # ReturnItem model
        migrations.CreateModel(
            name='ReturnItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tenant_id', models.IntegerField(db_index=True)),
                ('quantity_returned', models.PositiveIntegerField()),
                ('condition', models.CharField(
                    choices=[
                        ('as_new', 'As New'),
                        ('used', 'Used'),
                        ('damaged', 'Damaged'),
                        ('defective', 'Defective'),
                    ],
                    max_length=20,
                )),
                ('refund_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('approved', 'Approved'),
                        ('rejected', 'Rejected'),
                        ('refunded', 'Refunded'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('order_item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='return_items', to='orders.orderitem')),
                ('rma', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='orders.rma')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['rma_id'], name='orders_retu_rma_id_123abc_idx'),
                    models.Index(fields=['order_item_id'], name='orders_retu_order_i_456def_idx'),
                ],
            },
        ),

        # RefundTransaction model
        migrations.CreateModel(
            name='RefundTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tenant_id', models.IntegerField(db_index=True)),
                ('store_id', models.IntegerField(db_index=True)),
                ('refund_id', models.CharField(db_index=True, max_length=64, unique=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('currency', models.CharField(default='SAR', max_length=10)),
                ('refund_reason', models.CharField(blank=True, default='', max_length=255)),
                ('status', models.CharField(
                    choices=[
                        ('initiated', 'Initiated'),
                        ('processing', 'Processing'),
                        ('completed', 'Completed'),
                        ('failed', 'Failed'),
                        ('cancelled', 'Cancelled'),
                    ],
                    default='initiated',
                    max_length=20,
                )),
                ('gateway_response', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='refunds', to='orders.order')),
                ('rma', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='refunds', to='orders.rma')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['order_id'], name='orders_refu_order_i_123abc_idx'),
                    models.Index(fields=['rma_id'], name='orders_refu_rma_id_456def_idx'),
                    models.Index(fields=['status'], name='orders_refu_status_789ghi_idx'),
                ],
            },
        ),
    ]

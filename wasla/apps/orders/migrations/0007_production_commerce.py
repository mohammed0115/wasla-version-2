# Generated migration for production commerce order system

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0006_merge_20260228_0752"),
    ]

    operations = [
        # Add fields to Order model
        migrations.AddField(
            model_name="order",
            name="subtotal",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="order",
            name="tax_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="order",
            name="tax_rate",
            field=models.DecimalField(decimal_places=2, default="0.15", max_digits=5),
        ),
        migrations.AddField(
            model_name="order",
            name="refunded_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="order",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["tenant_id", "status"], name="orders_orde_tenant__db7d8c_idx"),
        ),
        
        # StockReservation model
        migrations.CreateModel(
            name="StockReservation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("quantity", models.PositiveIntegerField()),
                ("status", models.CharField(
                    choices=[
                        ("reserved", "Reserved"),
                        ("confirmed", "Confirmed"),
                        ("released", "Released"),
                    ],
                    default="reserved",
                    max_length=20,
                )),
                ("reserved_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                ("order_item", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="stock_reservation", to="orders.orderitem")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock_reservations", to="catalog.product")),
                ("variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="catalog.productvariant")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["tenant_id", "status"], name="orders_stock_tenant__idx"),
                    models.Index(fields=["product", "status"], name="orders_stock_product_idx"),
                    models.Index(fields=["expires_at"], name="orders_stock_expires_idx"),
                ],
            },
        ),
        
        # ShipmentLineItem model (for partial shipments)
        migrations.CreateModel(
            name="ShipmentLineItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("quantity_shipped", models.PositiveIntegerField()),
                ("order_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="orders.orderitem")),
                ("shipment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="line_items", to="shipping.shipment")),
            ],
            options={
                "unique_together": {("shipment", "order_item")},
                "indexes": [
                    models.Index(fields=["tenant_id"], name="orders_ship_tenant_idx"),
                ],
            },
        ),
        
        # RMA (Return Merchandise Authorization) model
        migrations.CreateModel(
            name="ReturnMerchandiseAuthorization",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("rma_number", models.CharField(max_length=32, unique=True)),
                ("reason", models.CharField(
                    choices=[
                        ("defective", "Defective"),
                        ("damaged_in_transit", "Damaged in Transit"),
                        ("not_as_described", "Not as Described"),
                        ("wrong_item", "Wrong Item"),
                        ("customer_request", "Customer Request"),
                        ("other", "Other"),
                    ],
                    max_length=50,
                )),
                ("reason_notes", models.TextField(blank=True, default="")),
                ("status", models.CharField(
                    choices=[
                        ("requested", "Requested"),
                        ("approved", "Approved"),
                        ("rejected", "Rejected"),
                        ("received", "Received"),
                        ("processed", "Processed"),
                    ],
                    default="requested",
                    max_length=20,
                )),
                ("customer_notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rmas", to="orders.order")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["tenant_id", "status"], name="orders_rma_tenant_idx"),
                    models.Index(fields=["order"], name="orders_rma_order_idx"),
                ],
            },
        ),
        
        # ReturnItem model
        migrations.CreateModel(
            name="ReturnItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("quantity_returned", models.PositiveIntegerField()),
                ("condition", models.CharField(
                    choices=[
                        ("new", "New"),
                        ("like_new", "Like New"),
                        ("good", "Good"),
                        ("fair", "Fair"),
                        ("defective", "Defective"),
                    ],
                    default="good",
                    max_length=20,
                )),
                ("order_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="orders.orderitem")),
                ("rma", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="orders.returmmerchandiseauthorization")),
            ],
            options={
                "unique_together": {("rma", "order_item")},
                "indexes": [
                    models.Index(fields=["tenant_id"], name="orders_return_tenant_idx"),
                ],
            },
        ),
        
        # Invoice model
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("invoice_number", models.CharField(max_length=32, unique=True)),
                ("series_prefix", models.CharField(default="INV", max_length=10)),
                ("status", models.CharField(
                    choices=[
                        ("draft", "Draft"),
                        ("issued", "Issued"),
                        ("paid", "Paid"),
                        ("partially_paid", "Partially Paid"),
                        ("overdue", "Overdue"),
                        ("cancelled", "Cancelled"),
                        ("credited", "Credited Memo"),
                    ],
                    default="draft",
                    max_length=20,
                )),
                ("subtotal", models.DecimalField(decimal_places=2, max_digits=12)),
                ("tax_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("discount_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("shipping_charge", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("total_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("issue_date", models.DateField(auto_now_add=True)),
                ("due_date", models.DateField()),
                ("paid_date", models.DateField(blank=True, null=True)),
                ("pdf_file", models.FileField(blank=True, null=True, upload_to="invoices/%Y/%m/")),
                ("seller_vat_number", models.CharField(blank=True, default="", max_length=50)),
                ("buyer_vat_number", models.CharField(blank=True, default="", max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="invoice", to="orders.order")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["tenant_id", "status"], name="orders_inv_tenant_idx"),
                    models.Index(fields=["order"], name="orders_inv_order_idx"),
                    models.Index(fields=["issue_date"], name="orders_inv_date_idx"),
                ],
            },
        ),
        
        # RefundTransaction model
        migrations.CreateModel(
            name="RefundTransaction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(default="SAR", max_length=10)),
                ("provider", models.CharField(blank=True, default="", max_length=50)),
                ("provider_refund_id", models.CharField(blank=True, default="", max_length=255)),
                ("status", models.CharField(
                    choices=[
                        ("pending", "Pending"),
                        ("processing", "Processing"),
                        ("completed", "Completed"),
                        ("failed", "Failed"),
                    ],
                    default="pending",
                    max_length=20,
                )),
                ("reason", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="refunds", to="orders.order")),
                ("rma", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="refunds", to="orders.returmmerchandiseauthorization")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["tenant_id", "status"], name="orders_refund_tenant_idx"),
                    models.Index(fields=["order"], name="orders_refund_order_idx"),
                    models.Index(fields=["provider_refund_id"], name="orders_refund_prov_idx"),
                ],
            },
        ),
    ]

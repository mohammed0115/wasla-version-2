# Generated manually for wallet operational accounting

import django.db.models.deletion
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("wallet", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="wallet",
            name="tenant_id",
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="wallet",
            name="available_balance",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="wallet",
            name="pending_balance",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="wallettransaction",
            name="tenant_id",
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="wallettransaction",
            name="balance_bucket",
            field=models.CharField(
                choices=[("available", "Available"), ("pending", "Pending")],
                default="available",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="wallettransaction",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("order_paid", "Order Paid"),
                    ("order_delivered", "Order Delivered"),
                    ("refund", "Refund"),
                    ("withdrawal", "Withdrawal"),
                    ("adjustment", "Adjustment"),
                ],
                default="adjustment",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="wallettransaction",
            name="metadata_json",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddConstraint(
            model_name="wallet",
            constraint=models.UniqueConstraint(fields=("store_id",), name="uq_wallet_store"),
        ),
        migrations.AddIndex(
            model_name="wallet",
            index=models.Index(fields=["tenant_id", "store_id"], name="wallet_wallet_tenant__ff6e19_idx"),
        ),
        migrations.AddIndex(
            model_name="wallettransaction",
            index=models.Index(fields=["tenant_id", "created_at"], name="wallet_walle_tenant__d4e348_idx"),
        ),
        migrations.AddIndex(
            model_name="wallettransaction",
            index=models.Index(fields=["wallet", "created_at"], name="wallet_walle_wallet__12d34a_idx"),
        ),
        migrations.AddIndex(
            model_name="wallettransaction",
            index=models.Index(fields=["wallet", "event_type"], name="wallet_walle_wallet__6c44a1_idx"),
        ),
        migrations.AddIndex(
            model_name="wallettransaction",
            index=models.Index(fields=["reference"], name="wallet_walle_referen_0bf72e_idx"),
        ),
        migrations.CreateModel(
            name="WithdrawalRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tenant_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("store_id", models.IntegerField(db_index=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("paid", "Paid"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("requested_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("note", models.CharField(blank=True, default="", max_length=255)),
                ("processed_by_user_id", models.IntegerField(blank=True, null=True)),
                (
                    "wallet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="withdrawal_requests",
                        to="wallet.wallet",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="withdrawalrequest",
            index=models.Index(fields=["tenant_id", "status"], name="wallet_with_tenant__7b79d7_idx"),
        ),
        migrations.AddIndex(
            model_name="withdrawalrequest",
            index=models.Index(fields=["store_id", "requested_at"], name="wallet_with_store_i_d22a42_idx"),
        ),
    ]

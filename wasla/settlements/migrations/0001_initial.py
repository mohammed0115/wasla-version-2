from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("orders", "0003_order_checkout_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("actor_id", models.IntegerField(blank=True, null=True)),
                ("store_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("action", models.CharField(max_length=100)),
                ("payload_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="LedgerAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_id", models.IntegerField(db_index=True)),
                ("currency", models.CharField(default="SAR", max_length=10)),
                ("available_balance", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("pending_balance", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Settlement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_id", models.IntegerField(db_index=True)),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("gross_amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("fees_amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("net_amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("created", "Created"),
                            ("approved", "Approved"),
                            ("paid", "Paid"),
                            ("failed", "Failed"),
                        ],
                        default="created",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="SettlementItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("fee_amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("net_amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                (
                    "order",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="settlement_items", to="orders.order"),
                ),
                (
                    "settlement",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="settlements.settlement"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="LedgerEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_id", models.IntegerField(db_index=True)),
                (
                    "entry_type",
                    models.CharField(choices=[("debit", "Debit"), ("credit", "Credit")], max_length=10),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("currency", models.CharField(default="SAR", max_length=10)),
                ("description", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ledger_entries",
                        to="orders.order",
                    ),
                ),
                (
                    "settlement",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ledger_entries",
                        to="settlements.settlement",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["store_id", "created_at"], name="auditlog_store_created_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["action"], name="auditlog_action_idx"),
        ),
        migrations.AddIndex(
            model_name="ledgeraccount",
            index=models.Index(fields=["store_id", "currency"], name="ledgeraccount_store_currency_idx"),
        ),
        migrations.AddConstraint(
            model_name="ledgeraccount",
            constraint=models.UniqueConstraint(
                fields=("store_id", "currency"), name="uq_ledger_account_store_currency"
            ),
        ),
        migrations.AddIndex(
            model_name="ledgerentry",
            index=models.Index(fields=["store_id", "created_at"], name="ledgerentry_store_created_idx"),
        ),
        migrations.AddIndex(
            model_name="ledgerentry",
            index=models.Index(fields=["store_id", "entry_type"], name="ledgerentry_store_type_idx"),
        ),
        migrations.AddConstraint(
            model_name="ledgerentry",
            constraint=models.UniqueConstraint(fields=("order",), name="uq_ledger_entry_order"),
        ),
        migrations.AddIndex(
            model_name="settlement",
            index=models.Index(fields=["store_id", "created_at"], name="settlement_store_created_idx"),
        ),
        migrations.AddIndex(
            model_name="settlement",
            index=models.Index(fields=["store_id", "status"], name="settlement_store_status_idx"),
        ),
        migrations.AddIndex(
            model_name="settlementitem",
            index=models.Index(fields=["settlement", "order"], name="settleitem_settlement_order_idx"),
        ),
        migrations.AddConstraint(
            model_name="settlementitem",
            constraint=models.UniqueConstraint(fields=("order",), name="uq_settlement_item_order"),
        ),
    ]

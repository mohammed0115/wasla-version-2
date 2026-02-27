import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0013_payment_security_fields_backfill"),
        ("orders", "0001_initial"),
        ("stores", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentRisk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tenant_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("risk_score", models.IntegerField(default=0, help_text="Total risk score 0-100")),
                ("risk_level", models.CharField(choices=[("low", "Low (0-25)"), ("medium", "Medium (26-50)"), ("high", "High (51-75)"), ("critical", "Critical (76-100)")], db_index=True, default="low", max_length=20)),
                ("flagged", models.BooleanField(db_index=True, default=False, help_text="Flagged for manual review")),
                ("ip_address", models.GenericIPAddressField(blank=True, help_text="Customer IP address", null=True)),
                ("velocity_count_5min", models.IntegerField(default=0, help_text="Payments from same IP in last 5 minutes")),
                ("velocity_count_1hour", models.IntegerField(default=0, help_text="Payments from same IP in last 1 hour")),
                ("velocity_amount_5min", models.DecimalField(decimal_places=2, default=0, help_text="Total amount from same IP in last 5 minutes", max_digits=14)),
                ("refund_rate_percent", models.DecimalField(decimal_places=2, default=0, help_text="Historical refund rate for this customer", max_digits=5)),
                ("previous_failed_attempts", models.IntegerField(default=0, help_text="Count of failed payment attempts")),
                ("is_new_customer", models.BooleanField(default=False, help_text="Customer's first purchase")),
                ("unusual_amount", models.BooleanField(default=False, help_text="Amount significantly higher than average")),
                ("triggered_rules", models.JSONField(blank=True, default=list, help_text="List of risk rules that triggered")),
                ("reviewed", models.BooleanField(db_index=True, default=False)),
                ("reviewed_by", models.CharField(blank=True, default="", help_text="Admin user who reviewed this", max_length=120)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_decision", models.CharField(choices=[("approved", "Approved"), ("rejected", "Rejected"), ("pending", "Pending")], default="pending", max_length=20)),
                ("review_notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payment_risks", to="orders.order")),
                ("payment_attempt", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="risk_assessment", to="payments.paymentattempt")),
                ("store", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="payment_risks", to="stores.store")),
            ],
        ),
        migrations.AddIndex(
            model_name="paymentrisk",
            index=models.Index(fields=["store", "flagged", "created_at"], name="payments_pr_store_f_created_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentrisk",
            index=models.Index(fields=["risk_level", "reviewed"], name="payments_pr_risk_reviewed_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentrisk",
            index=models.Index(fields=["ip_address", "created_at"], name="payments_pr_ip_created_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentrisk",
            index=models.Index(fields=["order"], name="payments_pr_order_idx"),
        ),
    ]

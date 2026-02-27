import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0011_rename_payments_pr_provide_7a8f2c_idx_payments_pr_provide_200664_idx_and_more"),
        ("stores", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentattempt",
            name="idempotency_key",
            field=models.CharField(db_index=True, max_length=128),
        ),
        migrations.AlterField(
            model_name="paymentattempt",
            name="status",
            field=models.CharField(
                choices=[
                    ("initiated", "Initiated"),
                    ("pending", "Pending"),
                    ("confirmed", "Confirmed"),
                    ("failed", "Failed"),
                    ("refunded", "Refunded"),
                    ("flagged", "Flagged"),
                    ("retry_pending", "Retry Pending"),
                    ("cancelled", "Cancelled"),
                ],
                default="initiated",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentattempt",
            constraint=models.UniqueConstraint(
                fields=("store", "order", "idempotency_key"),
                name="uq_payment_attempt_store_order_idempotency",
            ),
        ),
        migrations.AddField(
            model_name="webhookevent",
            name="processed",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="webhookevent",
            name="store",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="payment_webhook_events",
                to="stores.store",
            ),
        ),
        migrations.AddField(
            model_name="webhookevent",
            name="provider_name",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="webhookevent",
            name="raw_payload",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="webhookevent",
            name="signature_valid",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AlterField(
            model_name="webhookevent",
            name="status",
            field=models.CharField(
                choices=[
                    ("received", "Received"),
                    ("processing", "Processing"),
                    ("ignored", "Ignored"),
                    ("processed", "Processed"),
                    ("failed", "Failed"),
                ],
                db_index=True,
                default="received",
                max_length=20,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="webhookevent",
            name="uq_payment_webhook_provider_event",
        ),
        migrations.AddConstraint(
            model_name="webhookevent",
            constraint=models.UniqueConstraint(
                fields=("store", "event_id"),
                name="uq_payment_webhook_store_event",
            ),
        ),
        migrations.AddField(
            model_name="paymentprovidersettings",
            name="retry_max_attempts",
            field=models.IntegerField(default=3),
        ),
        migrations.AddField(
            model_name="paymentprovidersettings",
            name="webhook_tolerance_seconds",
            field=models.IntegerField(default=300),
        ),
    ]

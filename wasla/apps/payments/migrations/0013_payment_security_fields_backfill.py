import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0008_payment_security_hardening"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentattempt",
            name="retry_count",
            field=models.IntegerField(default=0, help_text="Number of retry attempts"),
        ),
        migrations.AddField(
            model_name="paymentattempt",
            name="last_retry_at",
            field=models.DateTimeField(blank=True, null=True, help_text="Timestamp of last retry"),
        ),
        migrations.AddField(
            model_name="paymentattempt",
            name="next_retry_after",
            field=models.DateTimeField(blank=True, null=True, help_text="When to retry next (exponential backoff)"),
        ),
        migrations.AddField(
            model_name="paymentattempt",
            name="retry_pending",
            field=models.BooleanField(default=False, help_text="Waiting for retry after timeout"),
        ),
        migrations.AddField(
            model_name="paymentattempt",
            name="ip_address",
            field=models.GenericIPAddressField(blank=True, null=True, help_text="Customer IP address from request"),
        ),
        migrations.AddField(
            model_name="paymentattempt",
            name="user_agent",
            field=models.TextField(blank=True, default="", help_text="User agent from client request"),
        ),
        migrations.AddField(
            model_name="paymentattempt",
            name="webhook_received",
            field=models.BooleanField(default=False, help_text="Webhook confirmation received"),
        ),
        migrations.AddField(
            model_name="paymentattempt",
            name="webhook_verified",
            field=models.BooleanField(default=False, help_text="Webhook signature verified"),
        ),
        migrations.AddField(
            model_name="paymentattempt",
            name="webhook_event",
            field=models.ForeignKey(
                blank=True,
                help_text="Webhook that confirmed this payment",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payment_attempts",
                to="payments.webhookevent",
            ),
        ),
        migrations.AddField(
            model_name="webhookevent",
            name="payload_hash",
            field=models.CharField(blank=True, default="", help_text="SHA256 hash of payload for integrity", max_length=64),
        ),
        migrations.AddField(
            model_name="webhookevent",
            name="timestamp_tolerance_seconds",
            field=models.IntegerField(default=300, help_text="Tolerance for timestamp validation (5 min default)"),
        ),
        migrations.AddField(
            model_name="webhookevent",
            name="retry_count",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="webhookevent",
            name="last_error",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="webhookevent",
            name="idempotency_checked",
            field=models.BooleanField(default=False, help_text="Whether idempotency was verified"),
        ),
    ]

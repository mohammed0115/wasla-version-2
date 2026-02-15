from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0002_order_store_id_alter_order_status_and_more"),
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentIntent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_id", models.IntegerField(db_index=True)),
                ("provider_code", models.CharField(max_length=50)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(default="SAR", max_length=10)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("requires_action", "Requires action"), ("succeeded", "Succeeded"), ("failed", "Failed")], default="pending", max_length=32)),
                ("provider_reference", models.CharField(blank=True, default="", max_length=120)),
                ("idempotency_key", models.CharField(max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payment_intents",
                        to="orders.order",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PaymentEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider_code", models.CharField(max_length=50)),
                ("event_id", models.CharField(max_length=120)),
                ("payload_json", models.JSONField(blank=True, default=dict)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddIndex(
            model_name="paymentintent",
            index=models.Index(fields=["store_id", "provider_code", "status"], name="payments_pa_store_i_5f64f3_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentintent",
            index=models.Index(fields=["provider_code", "provider_reference"], name="payments_pa_provider_6bde6f_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentevent",
            index=models.Index(fields=["provider_code", "event_id"], name="payments_pa_provider_9a3f7a_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentevent",
            index=models.Index(fields=["received_at"], name="payments_pa_received_7c69c2_idx"),
        ),
    ]

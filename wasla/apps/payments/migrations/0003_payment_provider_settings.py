from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0002_payment_intent_and_events"),
        ("tenants", "0007_storepaymentsettings_storeshippingsettings_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentevent",
            name="payload_raw",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.CreateModel(
            name="PaymentProviderSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_providers",
                        to="tenants.tenant",
                    ),
                ),
                ("provider_code", models.CharField(max_length=50)),
                ("display_name", models.CharField(blank=True, default="", max_length=120)),
                ("is_enabled", models.BooleanField(default=False)),
                ("credentials", models.JSONField(blank=True, default=dict)),
                ("webhook_secret", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name="paymentprovidersettings",
            constraint=models.UniqueConstraint(fields=("tenant", "provider_code"), name="uq_payment_provider_tenant_code"),
        ),
        migrations.AddIndex(
            model_name="paymentprovidersettings",
            index=models.Index(fields=["tenant", "is_enabled"], name="payments_pa_tenant__1f443c_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentprovidersettings",
            index=models.Index(fields=["provider_code", "is_enabled"], name="payments_pa_provid_66e7d2_idx"),
        ),
    ]

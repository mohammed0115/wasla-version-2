from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("cart", "0001_initial"),
        ("orders", "0002_order_store_id_alter_order_status_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="CheckoutSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_id", models.IntegerField(db_index=True)),
                ("status", models.CharField(choices=[("ADDRESS", "Address"), ("SHIPPING", "Shipping"), ("PAYMENT", "Payment"), ("CONFIRMED", "Confirmed")], default="ADDRESS", max_length=20)),
                ("shipping_address_json", models.JSONField(blank=True, default=dict)),
                ("shipping_method_code", models.CharField(blank=True, default="", max_length=64)),
                ("totals_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "cart",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="checkout_sessions",
                        to="cart.cart",
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="checkout_sessions",
                        to="orders.order",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="checkoutsession",
            index=models.Index(fields=["store_id", "status"], name="checkout_che_store_i_79fd32_idx"),
        ),
        migrations.AddIndex(
            model_name="checkoutsession",
            index=models.Index(fields=["store_id", "created_at"], name="checkout_che_store_i_67ed5c_idx"),
        ),
    ]

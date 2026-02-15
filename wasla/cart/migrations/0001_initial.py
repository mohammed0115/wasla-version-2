from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Cart",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_id", models.IntegerField(db_index=True)),
                ("session_key", models.CharField(blank=True, default=None, max_length=64, null=True)),
                ("currency", models.CharField(default="SAR", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="carts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CartItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField()),
                ("unit_price_snapshot", models.DecimalField(decimal_places=2, max_digits=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "cart",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="items", to="cart.cart"
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="catalog.product"),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="cart",
            index=models.Index(fields=["store_id", "updated_at"], name="cart_cart_store_i_9c64b3_idx"),
        ),
        migrations.AddConstraint(
            model_name="cart",
            constraint=models.UniqueConstraint(fields=("store_id", "user"), name="uq_cart_store_user"),
        ),
        migrations.AddConstraint(
            model_name="cart",
            constraint=models.UniqueConstraint(fields=("store_id", "session_key"), name="uq_cart_store_session"),
        ),
        migrations.AddIndex(
            model_name="cartitem",
            index=models.Index(fields=["cart", "created_at"], name="cart_cartit_cart_id_0b2f4b_idx"),
        ),
        migrations.AddConstraint(
            model_name="cartitem",
            constraint=models.UniqueConstraint(fields=("cart", "product"), name="uq_cart_item_cart_product"),
        ),
    ]

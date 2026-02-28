"""Initial migration for Coupons app."""

from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("stores", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Coupon",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", models.CharField(max_length=50, unique=True)),
                (
                    "discount_type",
                    models.CharField(
                        choices=[
                            ("percentage", "Percentage Discount (%)"),
                            ("fixed", "Fixed Amount Discount"),
                        ],
                        default="percentage",
                        max_length=20,
                    ),
                ),
                (
                    "discount_value",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "max_discount_amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=10,
                        null=True,
                    ),
                ),
                (
                    "minimum_purchase_amount",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "usage_limit",
                    models.IntegerField(blank=True, null=True),
                ),
                (
                    "usage_limit_per_customer",
                    models.IntegerField(
                        default=1,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                ("times_used", models.IntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("description", models.TextField(blank=True)),
                ("start_date", models.DateTimeField()),
                ("end_date", models.DateTimeField()),
                ("created_by", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="coupons",
                        to="stores.store",
                    ),
                ),
            ],
            options={
                "verbose_name": "Coupon",
                "verbose_name_plural": "Coupons",
                "db_table": "coupons_coupon",
            },
        ),
        migrations.CreateModel(
            name="CouponUsageLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "discount_applied",
                    models.DecimalField(decimal_places=2, max_digits=10),
                ),
                ("used_at", models.DateTimeField(auto_now_add=True)),
                (
                    "coupon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="usage_logs",
                        to="coupons.coupon",
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="coupon_usage_logs",
                        to="orders.order",
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="customers.customer",
                    ),
                ),
            ],
            options={
                "verbose_name": "Coupon Usage Log",
                "verbose_name_plural": "Coupon Usage Logs",
                "db_table": "coupons_usage_log",
            },
        ),
        migrations.AddConstraint(
            model_name="coupon",
            constraint=models.UniqueConstraint(
                fields=["store", "code"],
                name="unique_coupon_per_store",
            ),
        ),
        migrations.AddIndex(
            model_name="coupon",
            index=models.Index(fields=["store", "code"], name="coupons_cou_store_id_abc123_idx"),
        ),
        migrations.AddIndex(
            model_name="coupon",
            index=models.Index(fields=["store", "is_active"], name="coupons_cou_store_id_def456_idx"),
        ),
        migrations.AddIndex(
            model_name="coupon",
            index=models.Index(fields=["end_date"], name="coupons_cou_end_dat_ghi789_idx"),
        ),
        migrations.AddIndex(
            model_name="couponusagelog",
            index=models.Index(fields=["coupon", "customer"], name="coupons_cou_coupon__jkl012_idx"),
        ),
        migrations.AddIndex(
            model_name="couponusagelog",
            index=models.Index(fields=["used_at"], name="coupons_cou_used_at_mno345_idx"),
        ),
    ]

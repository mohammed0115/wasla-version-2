"""
Orders models (MVP).

AR:
- الطلب يمثل عملية شراء داخل متجر (`store_id`).
- OrderItem يمثل بنود الطلب المرتبطة بمنتجات الكتالوج.

EN:
- Order represents a purchase within a store (`store_id`).
- OrderItem represents line items linked to catalog products.
"""

from django.db import models

from apps.tenants.managers import TenantManager


class Order(models.Model):
    """Store-scoped order with a simple status lifecycle."""
    objects = TenantManager()

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    store_id = models.IntegerField(default=1, db_index=True)
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    order_number = models.CharField(max_length=32, unique=True)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    payment_status = models.CharField(max_length=20, default="pending")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="SAR")
    customer_name = models.CharField(max_length=255, blank=True, default="")
    customer_email = models.EmailField(blank=True, default="")
    customer_phone = models.CharField(max_length=32, blank=True, default="")
    shipping_address_json = models.JSONField(default=dict, blank=True)
    shipping_method_code = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.order_number

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "created_at"]),
            models.Index(fields=["store_id", "status"]),
        ]


class OrderItem(models.Model):
    """Line item belonging to an order."""
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.order} - {self.product} x{self.quantity}"

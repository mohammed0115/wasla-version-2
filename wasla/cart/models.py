from __future__ import annotations

from django.conf import settings
from django.db import models


class Cart(models.Model):
    store_id = models.IntegerField(db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="carts",
    )
    session_key = models.CharField(max_length=64, blank=True, null=True, default=None)
    currency = models.CharField(max_length=10, default="SAR")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["store_id", "user"], name="uq_cart_store_user"),
            models.UniqueConstraint(fields=["store_id", "session_key"], name="uq_cart_store_session"),
        ]
        indexes = [
            models.Index(fields=["store_id", "updated_at"]),
        ]

    def __str__(self) -> str:
        return f"Cart(store={self.store_id}, user={self.user_id}, session={self.session_key})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="uq_cart_item_cart_product"),
        ]
        indexes = [
            models.Index(fields=["cart", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.cart_id}:{self.product_id} x{self.quantity}"

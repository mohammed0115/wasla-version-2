from __future__ import annotations

from django.db import models


class CheckoutSession(models.Model):
    STATUS_ADDRESS = "ADDRESS"
    STATUS_SHIPPING = "SHIPPING"
    STATUS_PAYMENT = "PAYMENT"
    STATUS_CONFIRMED = "CONFIRMED"

    STATUS_CHOICES = [
        (STATUS_ADDRESS, "Address"),
        (STATUS_SHIPPING, "Shipping"),
        (STATUS_PAYMENT, "Payment"),
        (STATUS_CONFIRMED, "Confirmed"),
    ]

    store_id = models.IntegerField(db_index=True)
    cart = models.ForeignKey("cart.Cart", on_delete=models.CASCADE, related_name="checkout_sessions")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ADDRESS)
    shipping_address_json = models.JSONField(default=dict, blank=True)
    shipping_method_code = models.CharField(max_length=64, blank=True, default="")
    totals_json = models.JSONField(default=dict, blank=True)
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkout_sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "status"]),
            models.Index(fields=["store_id", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"CheckoutSession(store={self.store_id}, cart={self.cart_id}, status={self.status})"

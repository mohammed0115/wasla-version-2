from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta


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
    # Abandoned cart tracking
    abandoned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When cart was marked as abandoned (24h+ without activity)",
    )
    reminder_sent = models.BooleanField(
        default=False,
        help_text="Whether reminder email has been sent",
    )
    reminder_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When reminder email was sent",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["store_id", "user"], name="uq_cart_store_user"),
            models.UniqueConstraint(fields=["store_id", "session_key"], name="uq_cart_store_session"),
        ]
        indexes = [
            models.Index(fields=["store_id", "updated_at"]),
            models.Index(fields=["abandoned_at"]),
            models.Index(fields=["reminder_sent"]),
        ]

    def __str__(self) -> str:
        return f"Cart(store={self.store_id}, user={self.user_id}, session={self.session_key})"

    def is_abandoned(self, hours=24):
        """Check if cart is abandoned (no activity for X hours)."""
        if not self.updated_at:
            return False
        threshold = timezone.now() - timedelta(hours=hours)
        return self.updated_at < threshold

    def mark_abandoned(self):
        """Mark cart as abandoned."""
        if not self.abandoned_at and self.is_abandoned():
            self.abandoned_at = timezone.now()
            self.save(update_fields=["abandoned_at"])

    def get_item_value(self):
        """Get total cart value."""
        return sum(
            item.unit_price_snapshot * item.quantity
            for item in self.items.all()
        )

    def is_empty(self):
        """Check if cart has items."""
        return not self.items.exists()


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "product", "variant"], name="uq_cart_item_cart_product_variant"),
        ]
        indexes = [
            models.Index(fields=["cart", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.cart_id}:{self.product_id} x{self.quantity}"

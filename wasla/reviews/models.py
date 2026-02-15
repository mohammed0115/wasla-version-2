"""
Reviews models (MVP).

AR: تقييمات المنتجات مع حالات مراجعة (pending/approved/rejected).
EN: Product reviews with moderation statuses (pending/approved/rejected).
"""

from django.db import models

from catalog.models import Product
from customers.models import Customer


class Review(models.Model):
    """A rating/comment left by a customer for a product."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True)
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.product} - {self.rating} ({self.status})"

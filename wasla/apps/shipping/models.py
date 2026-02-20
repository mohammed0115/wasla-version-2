"""
Shipping models (MVP).

AR: شحنات مرتبطة بالطلبات (carrier + tracking + status).
EN: Shipments linked to orders (carrier + tracking + status).
"""

from django.db import models

from apps.tenants.managers import TenantManager


class Shipment(models.Model):
    """Shipment record linked to an order."""
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"

    STATUS_CHOICES = [
        ("ready", "Ready"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="shipments"
    )
    carrier = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ready")
    tracking_number = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.order} - {self.carrier}"

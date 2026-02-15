"""
Customers models (MVP).

AR:
- بيانات العملاء وعناوينهم.
- عزل المتاجر عبر `store_id`.

EN:
- Customer records and addresses.
- Tenant isolation via `store_id`.
"""

from django.db import models


class Customer(models.Model):
    """Customer profile within a store."""

    store_id = models.IntegerField(default=1, db_index=True)
    email = models.EmailField()
    full_name = models.CharField(max_length=255)
    group = models.CharField(max_length=50, default="retail")
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.full_name or self.email

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["store_id", "email"], name="uq_customer_store_email"),
        ]
        indexes = [
            models.Index(fields=["store_id", "is_active"]),
        ]


class Address(models.Model):
    """Customer address record."""

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="addresses")
    line1 = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.customer} - {self.city}, {self.country}"

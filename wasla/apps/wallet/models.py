"""
Wallet models (MVP).

AR:
- محفظة لكل متجر + معاملات credit/debit.
- هذا النموذج مبسّط وقد يحتاج لاحقًا لتطبيق Ledger كامل (Available/Pending…).

EN:
- A wallet per store with credit/debit transactions.
- This is a simplified model; it can be extended to a full ledger later.
"""

from django.db import models
from django.utils import timezone

from apps.tenants.managers import TenantManager


class Wallet(models.Model):
    """Wallet per store."""
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"

    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    store_id = models.IntegerField()
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    available_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    pending_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="USD")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["store_id"], name="uq_wallet_store"),
        ]
        indexes = [
            models.Index(fields=["tenant_id", "store_id"]),
        ]

    def __str__(self) -> str:
        return f"Store {self.store_id} ({self.currency})"


class WalletTransaction(models.Model):
    """Wallet ledger entry (credit/debit)."""
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"
    TRANSACTION_TYPES = [
        ("credit", "Credit"),
        ("debit", "Debit"),
    ]
    BALANCE_BUCKETS = [
        ("available", "Available"),
        ("pending", "Pending"),
    ]
    EVENT_TYPES = [
        ("order_paid", "Order Paid"),
        ("order_delivered", "Order Delivered"),
        ("refund", "Refund"),
        ("withdrawal", "Withdrawal"),
        ("adjustment", "Adjustment"),
    ]

    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="transactions")
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    balance_bucket = models.CharField(max_length=20, choices=BALANCE_BUCKETS, default="available")
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES, default="adjustment")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reference = models.CharField(max_length=255)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "created_at"]),
            models.Index(fields=["wallet", "created_at"]),
            models.Index(fields=["wallet", "event_type"]),
            models.Index(fields=["reference"]),
        ]

    def __str__(self) -> str:
        return f"{self.wallet} - {self.transaction_type} {self.amount}"


class WithdrawalRequest(models.Model):
    """Merchant withdrawal request to transfer available wallet balance out."""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_PAID = "paid"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_PAID, "Paid"),
    ]

    objects = TenantManager()
    TENANT_FIELD = "tenant_id"

    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    store_id = models.IntegerField(db_index=True)
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="withdrawal_requests")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    requested_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    reference_code = models.CharField(max_length=64, unique=True, db_index=True)
    note = models.CharField(max_length=255, blank=True, default="")
    processed_by_user_id = models.IntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "status"]),
            models.Index(fields=["store_id", "requested_at"]),
        ]

    def __str__(self) -> str:
        return f"withdrawal {self.id} store={self.store_id} status={self.status}"

"""
Settlement & Ledger models.

AR:
- حساب دفتر أستاذ لكل متجر مع رصيد مُعلَّق ومتاح.
- تسويات دورية تربط الطلبات المدفوعة وتُحوِّل الرصيد من معلّق إلى متاح ثم مدفوع.

EN:
- Ledger account per store with pending/available balances.
- Periodic settlements that move funds from pending to available then paid.
"""

from django.db import models

from apps.tenants.managers import TenantManager


class LedgerAccount(models.Model):
    """Ledger account per store/currency."""
    objects = TenantManager()

    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    store_id = models.IntegerField(db_index=True)
    currency = models.CharField(max_length=10, default="SAR")
    available_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    pending_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("store_id", "currency"), name="uq_ledger_account_store_currency"),
        ]
        indexes = [
            models.Index(fields=["store_id", "currency"]),
        ]

    def __str__(self) -> str:
        return f"Store {self.store_id} ({self.currency})"


class Settlement(models.Model):
    """Settlement for a time period."""
    objects = TenantManager()

    STATUS_CREATED = "created"
    STATUS_APPROVED = "approved"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_CREATED, "Created"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_PAID, "Paid"),
        (STATUS_FAILED, "Failed"),
    ]

    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    store_id = models.IntegerField(db_index=True)
    period_start = models.DateField()
    period_end = models.DateField()
    gross_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    fees_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CREATED)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "created_at"]),
            models.Index(fields=["store_id", "status"]),
        ]

    def __str__(self) -> str:
        return f"Settlement {self.id} (Store {self.store_id})"


class SettlementItem(models.Model):
    """Per-order settlement line."""
    objects = TenantManager()

    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    settlement = models.ForeignKey(Settlement, on_delete=models.CASCADE, related_name="items")
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="settlement_items")
    order_amount = models.DecimalField(max_digits=14, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("order",), name="uq_settlement_item_order"),
        ]
        indexes = [
            models.Index(fields=["settlement", "order"]),
        ]

    def __str__(self) -> str:
        return f"Settlement {self.settlement_id} - Order {self.order_id}"


class LedgerEntry(models.Model):
    """Ledger entry for credits/debits."""
    objects = TenantManager()

    TYPE_DEBIT = "debit"
    TYPE_CREDIT = "credit"

    ENTRY_TYPES = [
        (TYPE_DEBIT, "Debit"),
        (TYPE_CREDIT, "Credit"),
    ]

    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    store_id = models.IntegerField(db_index=True)
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    settlement = models.ForeignKey(
        Settlement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, default="SAR")
    description = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("order",), name="uq_ledger_entry_order"),
        ]
        indexes = [
            models.Index(fields=["store_id", "created_at"]),
            models.Index(fields=["store_id", "entry_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.entry_type} {self.amount} ({self.currency})"


class AuditLog(models.Model):
    """Audit log for admin actions."""
    objects = TenantManager()

    actor_id = models.IntegerField(null=True, blank=True)
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    store_id = models.IntegerField(null=True, blank=True, db_index=True)
    action = models.CharField(max_length=100)
    payload_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "created_at"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} ({self.store_id})"

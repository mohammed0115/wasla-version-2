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


class SettlementRecord(models.Model):
    """Per-successful-payment settlement record for Wasla fee accounting."""

    STATUS_PENDING = "pending"
    STATUS_INVOICED = "invoiced"
    STATUS_PAID = "paid"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_INVOICED, "Invoiced"),
        (STATUS_PAID, "Paid"),
    ]

    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.CASCADE,
        related_name="settlement_records",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="settlement_records",
    )
    payment_attempt = models.OneToOneField(
        "payments.PaymentAttempt",
        on_delete=models.PROTECT,
        related_name="settlement_record",
    )
    gross_amount = models.DecimalField(max_digits=14, decimal_places=2)
    wasla_fee = models.DecimalField(max_digits=14, decimal_places=2, default=1)
    net_amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["store", "status", "created_at"]),
            models.Index(fields=["order"]),
        ]

    def __str__(self) -> str:
        return f"SettlementRecord {self.id} - attempt {self.payment_attempt_id}"


class Invoice(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ISSUED = "issued"
    STATUS_PAID = "paid"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_ISSUED, "Issued"),
        (STATUS_PAID, "Paid"),
    ]

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="invoices",
    )
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    total_operations = models.PositiveIntegerField(default=0)
    total_wasla_fee = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "year", "month"),
                name="uq_invoice_tenant_year_month",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "year", "month"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Invoice {self.tenant_id}-{self.year}-{self.month:02d}"


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    settlement = models.OneToOneField(
        SettlementRecord,
        on_delete=models.PROTECT,
        related_name="invoice_line",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["invoice", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"InvoiceLine {self.invoice_id}:{self.settlement_id}"


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

class SettlementBatch(models.Model):
    """
    Settlement batch for grouping orders processed in one settlement run.
    
    Idempotent by design:
    - unique constraint on (store_id, batch_reference) prevents duplicates
    - idempotency_key ensures same task input always produces same result
    """
    
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_PARTIAL = "partial"  # Some orders succeeded, some failed
    
    STATUS_CHOICES = [
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_PARTIAL, "Partial"),
    ]
    
    objects = TenantManager()
    
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.CASCADE,
        related_name="settlement_batches",
    )
    batch_reference = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Unique identifier for this batch (e.g., BATCH-2026-02-25-001)",
    )
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="UUID to ensure idempotent processing",
    )
    
    # Batch content
    total_orders = models.PositiveIntegerField(default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_fees = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_net = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    # Processing metadata
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PROCESSING,
        db_index=True,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_reason = models.TextField(blank=True, default="")
    
    # Statistics
    orders_succeeded = models.PositiveIntegerField(default=0)
    orders_failed = models.PositiveIntegerField(default=0)
    
    # Timing
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("store", "batch_reference"),
                name="uq_settlement_batch_reference",
            ),
        ]
        indexes = [
            models.Index(fields=["store", "status", "created_at"]),
            models.Index(fields=["idempotency_key"]),
            models.Index(fields=["status", "created_at"]),
        ]
        ordering = ["-created_at"]
    
    def __str__(self) -> str:
        return f"Batch {self.batch_reference} ({self.status}) - {self.total_orders} orders"


class SettlementBatchItem(models.Model):
    """
    Individual order within a settlement batch.
    
    Tracks which orders are included in which batch for audit trail.
    """
    
    STATUS_INCLUDED = "included"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    
    STATUS_CHOICES = [
        (STATUS_INCLUDED, "Included"),
        (STATUS_PROCESSED, "Processed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SKIPPED, "Skipped"),
    ]
    
    batch = models.ForeignKey(
        SettlementBatch,
        on_delete=models.CASCADE,
        related_name="items",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="batch_items",
    )
    
    # Order snapshot (denormalized for audit)
    order_amount = models.DecimalField(max_digits=14, decimal_places=2)
    calculated_fee = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    calculated_net = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    # Processing result
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_INCLUDED,
    )
    error_message = models.TextField(blank=True, default="")
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("batch", "order"),
                name="uq_batch_item_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["batch", "status"]),
            models.Index(fields=["order"]),
        ]
    
    def __str__(self) -> str:
        return f"Batch {self.batch.batch_reference} - Order {self.order_id}"


class SettlementRunLog(models.Model):
    """
    Log entry for each settlement processing run.
    
    Provides observability and audit trail for automated settlement tasks.
    """
    
    STATUS_STARTED = "started"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    
    STATUS_CHOICES = [
        (STATUS_STARTED, "Started"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]
    
    objects = TenantManager()
    
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.CASCADE,
        related_name="settlement_run_logs",
        null=True,
        blank=True,
    )
    
    # Task info
    task_name = models.CharField(max_length=255, db_index=True)
    task_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    
    # Execution
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_STARTED,
        db_index=True,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    
    # Metadata
    message = models.TextField(blank=True, default="")
    payload_json = models.JSONField(default=dict, blank=True)
    error_trace = models.TextField(blank=True, default="")
    
    # Statistics
    orders_processed = models.PositiveIntegerField(default=0)
    batches_created = models.PositiveIntegerField(default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["task_name", "created_at"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["store", "created_at"]),
        ]
        ordering = ["-created_at"]
    
    def __str__(self) -> str:
        return f"{self.task_name} ({self.status}) - {self.created_at}"


class ReconciliationReport(models.Model):
    """
    Reconciliation report comparing payments vs settlements.
    
    Detects:
    - Missing settlements (paid orders not yet settled)
    - Over-settlement (more settled than paid)
    - Refund inconsistencies
    - Amount discrepancies
    """
    
    STATUS_OK = "ok"
    STATUS_WARNING = "warning"
    STATUS_ERROR = "error"
    
    STATUS_CHOICES = [
        (STATUS_OK, "OK"),
        (STATUS_WARNING, "Warning"),
        (STATUS_ERROR, "Error"),
    ]
    
    objects = TenantManager()
    
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.CASCADE,
        related_name="reconciliation_reports",
        null=True,
        blank=True,
    )
    
    # Period
    period_start = models.DateField(db_index=True)
    period_end = models.DateField(db_index=True)
    
    # Totals
    expected_total = models.DecimalField(max_digits=14, decimal_places=2)
    settled_total = models.DecimalField(max_digits=14, decimal_places=2)
    discrepancy = models.DecimalField(max_digits=14, decimal_places=2)
    discrepancy_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Detail counts
    unsettled_orders_count = models.PositiveIntegerField(default=0)
    orphaned_items_count = models.PositiveIntegerField(default=0)
    amount_mismatch_count = models.PositiveIntegerField(default=0)
    
    # Status and findings
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OK,
        db_index=True,
    )
    findings = models.JSONField(default=list, blank=True)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("store", "period_start", "period_end"),
                name="uq_reconciliation_report_period",
            ),
        ]
        indexes = [
            models.Index(fields=["store", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]
        ordering = ["-created_at"]
    
    def __str__(self) -> str:
        return f"Reconciliation {self.period_start} to {self.period_end} ({self.status})"
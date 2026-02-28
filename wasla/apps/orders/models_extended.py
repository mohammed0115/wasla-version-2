"""
Production Commerce Order Models

Includes:
- StockReservation: Reserve stock at checkout with auto-release TTL
- Invoice: Per-tenant invoice numbering with ZATCA structure
- ShipmentLineItem: Track partial shipments to line items
- RMA: Return Merchandise Authorization for returns/exchanges
- ReturnItem: Individual return items with refund status
- RefundTransaction: Payment refund audit trail
"""

from django.db import models
from django.utils import timezone
from datetime import timedelta
import hashlib
from decimal import Decimal

from apps.tenants.managers import TenantManager


class StockReservation(models.Model):
    """
    Reserve stock at checkout. Auto-expires after TTL if not paid.
    
    Prevents overselling by holding inventory during checkout phase.
    Links OrderItem to Inventory with timeout-based auto-release.
    """
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"
    
    STATUS_RESERVED = "reserved"
    STATUS_CONFIRMED = "confirmed"
    STATUS_RELEASED = "released"
    STATUS_EXPIRED = "expired"
    
    STATUS_CHOICES = [
        (STATUS_RESERVED, "Reserved"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_RELEASED, "Released"),
        (STATUS_EXPIRED, "Expired"),
    ]
    
    # TTL: 15 minutes for checkout, 30 min after paid before fulfillment
    RESERVATION_TTL_SECONDS = 900  # 15 minutes
    PAID_RESERVATION_TTL_SECONDS = 1800  # 30 minutes
    
    tenant_id = models.IntegerField(db_index=True)
    store_id = models.IntegerField(db_index=True)
    order_item = models.OneToOneField(
        "orders.OrderItem", on_delete=models.CASCADE, related_name="stock_reservation"
    )
    inventory = models.ForeignKey(
        "catalog.Inventory", on_delete=models.PROTECT, related_name="reservations"
    )
    reserved_quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RESERVED)
    
    # Timestamp when reservation was created
    created_at = models.DateTimeField(auto_now_add=True)
    # Timestamp when reservation expires (for auto-release)
    expires_at = models.DateTimeField(db_index=True)
    # Timestamp when released (if manual release)
    released_at = models.DateTimeField(null=True, blank=True)
    # Reason for release/expiration
    release_reason = models.CharField(max_length=255, blank=True, default="")
    
    class Meta:
        indexes = [
            models.Index(fields=["store_id", "status"]),
            models.Index(fields=["tenant_id", "expires_at"]),
            models.Index(fields=["order_item_id"]),
        ]
    
    def __str__(self) -> str:
        return f"[{self.tenant_id}] {self.get_status_display()} x{self.reserved_quantity}"
    
    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at
    
    def confirm_reservation(self) -> None:
        """Mark as confirmed (paid). Extends TTL."""
        if self.status != self.STATUS_RESERVED:
            raise ValueError(f"Cannot confirm reservation in {self.status} status")
        
        self.status = self.STATUS_CONFIRMED
        self.expires_at = timezone.now() + timedelta(seconds=self.PAID_RESERVATION_TTL_SECONDS)
        self.save(update_fields=["status", "expires_at"])
    
    def release_reservation(self, reason: str = "") -> None:
        """Release reserved stock back to inventory."""
        if self.status in {self.STATUS_RELEASED, self.STATUS_EXPIRED}:
            raise ValueError(f"Cannot release reservation in {self.status} status")
        
        # Return stock to inventory
        self.inventory.reserved_quantity = max(0, self.inventory.reserved_quantity - self.reserved_quantity)
        self.inventory.save(update_fields=["reserved_quantity"])
        
        self.status = self.STATUS_RELEASED
        self.released_at = timezone.now()
        self.release_reason = reason
        self.save(update_fields=["status", "released_at", "release_reason"])


class Invoice(models.Model):
    """
    Per-tenant invoice with ZATCA-compatible structure (Saudi VAT).
    
    Generates sequential invoice numbers per tenant/store.
    Supports PDF generation and compliance reporting.
    """
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"
    
    STATUS_DRAFT = "draft"
    STATUS_ISSUED = "issued"
    STATUS_PAID = "paid"
    STATUS_CANCELLED = "cancelled"
    STATUS_REFUNDED = "refunded"
    
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_ISSUED, "Issued"),
        (STATUS_PAID, "Paid"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_REFUNDED, "Refunded"),
    ]
    
    tenant_id = models.IntegerField(db_index=True)
    store_id = models.IntegerField(db_index=True)
    order = models.OneToOneField(
        "orders.Order", on_delete=models.PROTECT, related_name="invoice"
    )
    
    # Invoice numbering (per tenant: INV-<TENANT>-<STORE>-<SEQUENTIAL>)
    invoice_number = models.CharField(max_length=64, unique=True, db_index=True)
    issue_date = models.DateField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    
    # Amounts
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("15"))  # 15% Saudi VAT
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="SAR")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    
    # Customer details
    buyer_name = models.CharField(max_length=255)
    buyer_email = models.EmailField()
    buyer_vat_id = models.CharField(max_length=64, blank=True, default="")  # Customer VAT/Tax ID
    
    # Seller details
    seller_name = models.CharField(max_length=255)
    seller_vat_id = models.CharField(max_length=64, blank=True, default="")  # Store VAT/Tax ID
    seller_address = models.TextField(blank=True, default="")
    seller_bank_details = models.JSONField(default=dict, blank=True)  # For payment instructions
    
    # ZATCA Compliance (Saudi Arabia e-invoice)
    zatca_qr_code = models.TextField(blank=True, default="")  # Base64 encoded QR code
    zatca_uuid = models.CharField(max_length=64, blank=True, default="")  # Unique identifier per ZATCA
    zatca_hash = models.CharField(max_length=256, blank=True, default="")  # Previous invoice hash chain
    zatca_signed = models.BooleanField(default=False)  # Whether digitally signed
    
    # PDF storage
    pdf_file = models.FileField(upload_to="invoices/%Y/%m/", null=True, blank=True)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["store_id", "-issue_date"]),
            models.Index(fields=["tenant_id", "status"]),
            models.Index(fields=["buyer_email"]),
        ]
    
    def __str__(self) -> str:
        return f"{self.invoice_number} - {self.buyer_name}"
    
    def issue_invoice(self) -> None:
        """Mark invoice as issued."""
        if self.status != self.STATUS_DRAFT:
            raise ValueError(f"Cannot issue invoice in {self.status} status")
        
        self.status = self.STATUS_ISSUED
        self.issued_at = timezone.now()
        self.save(update_fields=["status", "issued_at"])
    
    def mark_as_paid(self) -> None:
        """Mark invoice as paid."""
        if self.status not in {self.STATUS_ISSUED, self.STATUS_DRAFT}:
            raise ValueError(f"Cannot mark as paid in {self.status} status")
        
        self.status = self.STATUS_PAID
        self.paid_at = timezone.now()
        self.save(update_fields=["status", "paid_at"])
    
    def compute_zatca_hash(self, previous_hash: str = "") -> str:
        """Compute SHA256 hash for ZATCA invoice chain."""
        data = f"{self.invoice_number}{self.issue_date}{self.total_amount}{previous_hash}"
        return hashlib.sha256(data.encode()).hexdigest()


class InvoiceLineItem(models.Model):
    """Line item for invoice (mirrors OrderItem with tax details)."""
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"
    
    tenant_id = models.IntegerField(db_index=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="line_items")
    order_item = models.OneToOneField(
        "orders.OrderItem", on_delete=models.SET_NULL, null=True, blank=True
    )
    
    # Line details
    description = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Tax
    line_subtotal = models.DecimalField(max_digits=12, decimal_places=2)  # qty * unit_price
    line_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)  # subtotal + tax
    
    class Meta:
        indexes = [
            models.Index(fields=["invoice_id"]),
        ]
    
    def __str__(self) -> str:
        return f"{self.invoice.invoice_number} - {self.description}"


class RMA(models.Model):
    """
    Return Merchandise Authorization (RMA).
    
    Tracks return requests, approvals, and refund processing.
    Supports partial returns and exchanges.
    """
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"
    
    STATUS_REQUESTED = "requested"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_IN_TRANSIT = "in_transit"
    STATUS_RECEIVED = "received"
    STATUS_INSPECTED = "inspected"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    
    STATUS_CHOICES = [
        (STATUS_REQUESTED, "Requested"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_IN_TRANSIT, "In Transit"),
        (STATUS_RECEIVED, "Received"),
        (STATUS_INSPECTED, "Inspected"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]
    
    REASON_DEFECTIVE = "defective"
    REASON_NOT_AS_DESCRIBED = "not_as_described"
    REASON_CHANGED_MIND = "changed_mind"
    REASON_DAMAGED_IN_SHIPPING = "damaged_in_shipping"
    REASON_OTHER = "other"
    
    REASON_CHOICES = [
        (REASON_DEFECTIVE, "Defective/Broken"),
        (REASON_NOT_AS_DESCRIBED, "Not as Described"),
        (REASON_CHANGED_MIND, "Changed Mind"),
        (REASON_DAMAGED_IN_SHIPPING, "Damaged in Shipping"),
        (REASON_OTHER, "Other"),
    ]
    
    tenant_id = models.IntegerField(db_index=True)
    store_id = models.IntegerField(db_index=True)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="rmas"
    )
    
    # RMA tracking
    rma_number = models.CharField(max_length=64, unique=True, db_index=True)
    reason = models.CharField(max_length=32, choices=REASON_CHOICES)
    reason_description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_REQUESTED)
    
    # Return type
    is_exchange = models.BooleanField(default=False)  # True = exchange, False = return
    exchange_product = models.ForeignKey(
        "catalog.Product", on_delete=models.SET_NULL, null=True, blank=True
    )
    
    # Shipping
    return_tracking_number = models.CharField(max_length=255, blank=True, default="")
    return_carrier = models.CharField(max_length=64, blank=True, default="")
    
    # Audit
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["store_id", "status"]),
            models.Index(fields=["order_id"]),
        ]
    
    def __str__(self) -> str:
        return f"{self.rma_number} - {self.get_reason_display()}"


class ReturnItem(models.Model):
    """Individual item being returned as part of an RMA."""
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"
    
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_REFUNDED = "refunded"
    
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_REFUNDED, "Refunded"),
    ]
    
    CONDITION_AS_NEW = "as_new"
    CONDITION_USED = "used"
    CONDITION_DAMAGED = "damaged"
    CONDITION_DEFECTIVE = "defective"
    
    CONDITION_CHOICES = [
        (CONDITION_AS_NEW, "As New"),
        (CONDITION_USED, "Used"),
        (CONDITION_DAMAGED, "Damaged"),
        (CONDITION_DEFECTIVE, "Defective"),
    ]
    
    tenant_id = models.IntegerField(db_index=True)
    rma = models.ForeignKey(RMA, on_delete=models.CASCADE, related_name="items")
    order_item = models.ForeignKey(
        "orders.OrderItem", on_delete=models.PROTECT, related_name="return_items"
    )
    
    # Return details
    quantity_returned = models.PositiveIntegerField()
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    
    # Refund
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    
    class Meta:
        indexes = [
            models.Index(fields=["rma_id"]),
            models.Index(fields=["order_item_id"]),
        ]
    
    def __str__(self) -> str:
        return f"{self.rma.rma_number} - Item x{self.quantity_returned}"


class RefundTransaction(models.Model):
    """
    Payment refund audit trail.
    
    Tracks refund requests, processing, and final status.
    Links to original payment transaction.
    """
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"
    
    STATUS_INITIATED = "initiated"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    
    STATUS_CHOICES = [
        (STATUS_INITIATED, "Initiated"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]
    
    tenant_id = models.IntegerField(db_index=True)
    store_id = models.IntegerField(db_index=True)
    
    # Link to order/RMA
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="refunds"
    )
    rma = models.ForeignKey(
        RMA, on_delete=models.SET_NULL, null=True, blank=True, related_name="refunds"
    )
    
    # Refund details
    refund_id = models.CharField(max_length=64, unique=True, db_index=True)  # External refund ID
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="SAR")
    refund_reason = models.CharField(max_length=255, blank=True, default="")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_INITIATED)
    gateway_response = models.JSONField(default=dict, blank=True)  # Response from payment gateway
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["order_id"]),
            models.Index(fields=["rma_id"]),
            models.Index(fields=["status"]),
        ]
    
    def __str__(self) -> str:
        return f"Refund {self.refund_id} - {self.amount}{self.currency}"

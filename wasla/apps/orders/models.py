"""
Orders models (MVP).

AR:
- الطلب يمثل عملية شراء داخل متجر (`store_id`).
- OrderItem يمثل بنود الطلب المرتبطة بمنتجات الكتالوج.

EN:
- Order represents a purchase within a store (`store_id`).
- OrderItem represents line items linked to catalog products.
"""

from django.db import models
from django.utils import timezone
from decimal import Decimal
import uuid
from dataclasses import dataclass

from apps.tenants.managers import TenantManager


@dataclass(frozen=True)
class ShippingAddress:
    full_name: str = ""
    email: str = ""
    phone: str = ""
    line1: str = ""
    line2: str = ""
    city: str = ""
    country: str = ""
    postal_code: str = ""


class Order(models.Model):
    """Store-scoped order with production commerce lifecycle."""
    objects = TenantManager()

    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_PROCESSING = "processing"
    STATUS_SHIPPED = "shipped"
    STATUS_DELIVERED = "delivered"
    STATUS_COMPLETED = "completed"
    STATUS_RETURNED = "returned"
    STATUS_PARTIALLY_REFUNDED = "partially_refunded"
    STATUS_REFUNDED = "refunded"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        # Core fulfillment flow
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_SHIPPED, "Shipped"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_COMPLETED, "Completed"),
        
        # Return & refund flow
        (STATUS_RETURNED, "Returned"),
        (STATUS_PARTIALLY_REFUNDED, "Partially Refunded"),
        (STATUS_REFUNDED, "Refunded"),
        
        # Terminal state
        (STATUS_CANCELLED, "Cancelled"),
    ]

    store_id = models.IntegerField(default=1, db_index=True)
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    order_number = models.CharField(max_length=32, unique=True)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    payment_status = models.CharField(max_length=20, default="pending")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # For invoicing
    currency = models.CharField(max_length=10, default="SAR")
    customer_name = models.CharField(max_length=255, blank=True, default="")
    customer_email = models.EmailField(blank=True, default="")
    customer_phone = models.CharField(max_length=32, blank=True, default="")
    shipping_address_json = models.JSONField(default=dict, blank=True)
    shipping_method_code = models.CharField(max_length=64, blank=True, default="")
    coupon_code = models.CharField(max_length=50, blank=True, default="")
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # VAT fields (ZATCA compatible)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.15"))  # 15% VAT default
    
    # Refund tracking
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Notification tracking
    confirmation_email_sent_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.order_number

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "created_at"]),
            models.Index(fields=["store_id", "status"]),
            models.Index(fields=["tenant_id", "status"]),
        ]

    @property
    def store(self):
        if hasattr(self, "_store_cache"):
            return self._store_cache
        from apps.stores.models import Store

        self._store_cache = Store.objects.filter(id=self.store_id).first()
        return self._store_cache

    @property
    def email(self) -> str:
        return self.customer_email or getattr(self.customer, "email", "") or ""

    @property
    def shipping_address(self):
        data = self.shipping_address_json or {}
        return ShippingAddress(
            full_name=data.get("full_name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            line1=data.get("line1", ""),
            line2=data.get("line2", ""),
            city=data.get("city", ""),
            country=data.get("country", ""),
            postal_code=data.get("postal_code", ""),
        )


class OrderItem(models.Model):
    """Line item belonging to an order."""
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.order} - {self.product} x{self.quantity}"

    @property
    def unit_price_snapshot(self):
        return self.price

    @property
    def total_price(self):
        return self.price * self.quantity


class StockReservation(models.Model):
    """
    Reserves stock at checkout to prevent overselling.
    Auto-releases on timeout (default 30 minutes).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE, related_name="stock_reservation")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="stock_reservations")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    
    STATUS_CHOICES = [
        ("reserved", "Reserved"),
        ("confirmed", "Confirmed"),  # Payment confirmed, hold until shipment
        ("released", "Released"),     # Cancelled or timeout
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="reserved")
    
    reserved_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()  # Timeout window
    confirmed_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    release_reason = models.CharField(max_length=255, blank=True, default="")
    
    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "status"]),
            models.Index(fields=["product", "status"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"StockReservation {self.id} - {self.product} x{self.quantity}"

    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())


class ShipmentLineItem(models.Model):
    """
    Maps OrderItem to Shipment with quantity breakdown.
    Enables partial shipments.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    shipment = models.ForeignKey("shipping.Shipment", on_delete=models.CASCADE, related_name="line_items")
    order_item = models.ForeignKey(OrderItem, on_delete=models.PROTECT)
    quantity_shipped = models.PositiveIntegerField()
    
    class Meta:
        unique_together = ("shipment", "order_item")
        indexes = [models.Index(fields=["tenant_id"])]

    def __str__(self) -> str:
        return f"{self.shipment} - {self.order_item.product} x{self.quantity_shipped}"


class ReturnMerchandiseAuthorization(models.Model):
    """
    RMA for returns and exchanges.
    Tracks customer returns and refund flow.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    store_id = models.IntegerField(null=True, blank=True, db_index=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="rmas")
    rma_number = models.CharField(max_length=32, unique=True)
    
    REASON_CHOICES = [
        ("defective", "Defective"),
        ("damaged_in_transit", "Damaged in Transit"),
        ("not_as_described", "Not as Described"),
        ("wrong_item", "Wrong Item"),
        ("customer_request", "Customer Request"),
        ("other", "Other"),
    ]
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    reason_description = models.TextField(blank=True, default="")
    
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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="requested")
    
    is_exchange = models.BooleanField(default=False)
    exchange_product = models.ForeignKey(
        "catalog.Product", on_delete=models.SET_NULL, null=True, blank=True
    )
    return_tracking_number = models.CharField(max_length=255, blank=True, default="")
    return_carrier = models.CharField(max_length=64, blank=True, default="")
    customer_notes = models.TextField(blank=True, default="")

    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "status"]),
            models.Index(fields=["order"]),
        ]

    def __str__(self) -> str:
        return self.rma_number


class ReturnItem(models.Model):
    """
    Individual items within an RMA.
    Maps to OrderItem with return quantity.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    rma = models.ForeignKey(ReturnMerchandiseAuthorization, on_delete=models.CASCADE, related_name="items")
    order_item = models.ForeignKey(OrderItem, on_delete=models.PROTECT)
    quantity_returned = models.PositiveIntegerField()
    
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
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default=CONDITION_USED)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    
    class Meta:
        unique_together = ("rma", "order_item")
        indexes = [models.Index(fields=["tenant_id"])]

    def __str__(self) -> str:
        return f"Return - {self.order_item.product} x{self.quantity_returned}"


class Invoice(models.Model):
    """
    Invoice model - ZATCA (Saudi VAT Authority) compatible.
    Supports PDF generation and VAT structure.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    store_id = models.IntegerField(null=True, blank=True, db_index=True)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="invoice")
    
    # Invoice numbering (per tenant)
    invoice_number = models.CharField(max_length=32, unique=True)
    series_prefix = models.CharField(max_length=10, default="INV")  # e.g., INV-2026-001
    
    STATUS_DRAFT = "draft"
    STATUS_ISSUED = "issued"
    STATUS_PAID = "paid"
    STATUS_PARTIALLY_PAID = "partially_paid"
    STATUS_OVERDUE = "overdue"
    STATUS_CANCELLED = "cancelled"
    STATUS_CREDITED = "credited"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_ISSUED, "Issued"),
        (STATUS_PAID, "Paid"),
        (STATUS_PARTIALLY_PAID, "Partially Paid"),
        (STATUS_OVERDUE, "Overdue"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_CREDITED, "Credited Memo"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    
    # Amounts
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("15"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="SAR")
    
    # Dates
    issue_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    
    # PDF storage
    pdf_file = models.FileField(upload_to="invoices/%Y/%m/", null=True, blank=True)
    
    # Customer details
    buyer_name = models.CharField(max_length=255, blank=True, default="")
    buyer_email = models.EmailField(blank=True, default="")
    buyer_vat_id = models.CharField(max_length=50, blank=True, default="")

    # Seller details
    seller_name = models.CharField(max_length=255, blank=True, default="")
    seller_vat_id = models.CharField(max_length=50, blank=True, default="")
    seller_address = models.TextField(blank=True, default="")
    seller_bank_details = models.JSONField(default=dict, blank=True)

    # ZATCA fields
    zatca_qr_code = models.TextField(blank=True, default="")
    zatca_uuid = models.CharField(max_length=64, blank=True, default="")
    zatca_hash = models.CharField(max_length=256, blank=True, default="")
    zatca_signed = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "status"]),
            models.Index(fields=["order"]),
            models.Index(fields=["issue_date"]),
        ]

    def __str__(self) -> str:
        return self.invoice_number

    def issue_invoice(self) -> None:
        if self.status != self.STATUS_DRAFT:
            raise ValueError(f"Cannot issue invoice in {self.status} status")
        self.status = self.STATUS_ISSUED
        self.issued_at = timezone.now()
        self.save(update_fields=["status", "issued_at"])

    def mark_as_paid(self) -> None:
        if self.status not in {self.STATUS_DRAFT, self.STATUS_ISSUED, self.STATUS_PARTIALLY_PAID}:
            raise ValueError(f"Cannot mark invoice paid in {self.status} status")
        self.status = self.STATUS_PAID
        self.paid_at = timezone.now()
        self.save(update_fields=["status", "paid_at"])


class InvoiceLineItem(models.Model):
    """Line item for invoice (mirrors OrderItem with tax details)."""
    objects = TenantManager()
    TENANT_FIELD = "tenant_id"

    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    store_id = models.IntegerField(null=True, blank=True, db_index=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="line_items")
    order_item = models.OneToOneField(
        "orders.OrderItem", on_delete=models.SET_NULL, null=True, blank=True
    )

    description = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    line_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        indexes = [
            models.Index(fields=["invoice_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.invoice_id}:{self.description}"


class RefundTransaction(models.Model):
    """
    Tracks refund transactions linked to RMA or direct refunds.
    Integrates with payment orchestrator.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    store_id = models.IntegerField(null=True, blank=True, db_index=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="refunds")
    rma = models.ForeignKey(ReturnMerchandiseAuthorization, on_delete=models.SET_NULL, null=True, blank=True, related_name="refunds")
    
    refund_id = models.CharField(max_length=64, unique=True, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="SAR")
    
    # Payment provider reference
    provider = models.CharField(max_length=50, blank=True, default="")  # tap, stripe, etc.
    provider_refund_id = models.CharField(max_length=255, blank=True, default="")
    
    STATUS_INITIATED = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_INITIATED, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_INITIATED)
    
    refund_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "status"]),
            models.Index(fields=["order"]),
            models.Index(fields=["provider_refund_id"]),
        ]

    def __str__(self) -> str:
        return f"Refund {self.id} - {self.amount} {self.currency}"


# Backward-compatible aliases
RMA = ReturnMerchandiseAuthorization

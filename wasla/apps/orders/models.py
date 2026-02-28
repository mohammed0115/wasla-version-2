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

from apps.tenants.managers import TenantManager


class Order(models.Model):
    """Store-scoped order with production commerce lifecycle."""
    objects = TenantManager()

    STATUS_CHOICES = [
        # Core fulfillment flow
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("completed", "Completed"),
        
        # Return & refund flow
        ("returned", "Returned"),
        ("partially_refunded", "Partially Refunded"),
        ("refunded", "Refunded"),
        
        # Terminal state
        ("cancelled", "Cancelled"),
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
    
    # VAT fields (ZATCA compatible)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.15"))  # 15% VAT default
    
    # Refund tracking
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
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
    
    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "status"]),
            models.Index(fields=["product", "status"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"StockReservation {self.id} - {self.product} x{self.quantity}"


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
    reason_notes = models.TextField(blank=True, default="")
    
    STATUS_CHOICES = [
        ("requested", "Requested"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("received", "Received"),
        ("processed", "Processed"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="requested")
    
    customer_notes = models.TextField(blank=True, default="")
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
    
    CONDITION_CHOICES = [
        ("new", "New"),
        ("like_new", "Like New"),
        ("good", "Good"),
        ("fair", "Fair"),
        ("defective", "Defective"),
    ]
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default="good")
    
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
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="invoice")
    
    # Invoice numbering (per tenant)
    invoice_number = models.CharField(max_length=32, unique=True)
    series_prefix = models.CharField(max_length=10, default="INV")  # e.g., INV-2026-001
    
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("issued", "Issued"),
        ("paid", "Paid"),
        ("partially_paid", "Partially Paid"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
        ("credited", "Credited Memo"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    
    # Amounts
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Dates
    issue_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    
    # PDF storage
    pdf_file = models.FileField(upload_to="invoices/%Y/%m/", null=True, blank=True)
    
    # VAT Registration (for ZATCA compliance)
    seller_vat_number = models.CharField(max_length=50, blank=True, default="")
    buyer_vat_number = models.CharField(max_length=50, blank=True, default="")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "status"]),
            models.Index(fields=["order"]),
            models.Index(fields=["issue_date"]),
        ]

    def __str__(self) -> str:
        return self.invoice_number


class RefundTransaction(models.Model):
    """
    Tracks refund transactions linked to RMA or direct refunds.
    Integrates with payment orchestrator.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="refunds")
    rma = models.ForeignKey(ReturnMerchandiseAuthorization, on_delete=models.SET_NULL, null=True, blank=True, related_name="refunds")
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="SAR")
    
    # Payment provider reference
    provider = models.CharField(max_length=50, blank=True, default="")  # tap, stripe, etc.
    provider_refund_id = models.CharField(max_length=255, blank=True, default="")
    
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    
    reason = models.TextField(blank=True, default="")
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

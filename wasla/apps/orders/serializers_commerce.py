"""
Serializers for production commerce models

Includes:
- InvoiceSerializer with line items
- RMASerializer with return items
- RefundTransactionSerializer
- StockReservationSerializer
"""

from rest_framework import serializers
from django.utils import timezone
from wasla.apps.orders.models import (
    Invoice,
    InvoiceLineItem,
    RMA,
    ReturnItem,
    RefundTransaction,
    StockReservation,
)


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    """Serializer for invoice line items"""
    
    product_name = serializers.CharField(source='order_item.product.name', read_only=True)
    sku = serializers.SerializerMethodField()
    
    class Meta:
        model = InvoiceLineItem
        fields = [
            'id',
            'description',
            'sku',
            'product_name',
            'quantity',
            'unit_price',
            'line_subtotal',
            'line_tax',
            'line_total',
        ]
        read_only_fields = ['id']
    
    def get_sku(self, obj):
        """Get SKU from related order item if available"""
        return obj.order_item.product.sku if obj.order_item else obj.sku


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer for invoices with line items and ZATCA details"""
    
    line_items = InvoiceLineItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='buyer_name')
    customer_email = serializers.CharField(source='buyer_email')
    
    class Meta:
        model = Invoice
        fields = [
            'id',
            'invoice_number',
            'issue_date',
            'due_date',
            'subtotal',
            'tax_amount',
            'tax_rate',
            'discount_amount',
            'shipping_cost',
            'total_amount',
            'currency',
            'status',
            'customer_name',
            'customer_email',
            'buyer_vat_id',
            'seller_name',
            'seller_vat_id',
            'zatca_qr_code',
            'zatca_hash',
            'zatca_uuid',
            'zatca_signed',
            'line_items',
            'created_at',
            'issued_at',
            'paid_at',
        ]
        read_only_fields = [
            'id',
            'invoice_number',
            'issue_date',
            'created_at',
            'issued_at',
            'paid_at',
            'line_items',
            'zatca_qr_code',
            'zatca_hash',
            'zatca_uuid',
            'zatca_signed',
        ]


class InvoiceCreateSerializer(serializers.Serializer):
    """Serializer for creating invoice from order"""
    
    order_id = serializers.IntegerField()
    tax_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        default='15.00',
        required=False,
    )
    
    def validate_order_id(self, value):
        """Validate order exists and is paid"""
        from wasla.apps.orders.models import Order
        try:
            order = Order.objects.get(id=value)
            if order.status not in ['paid', 'processing', 'shipped', 'delivered', 'completed']:
                raise serializers.ValidationError("Order must be paid or later status to create invoice")
            return value
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found")


class InvoiceGeneratePDFSerializer(serializers.Serializer):
    """Serializer for requesting PDF generation"""
    
    invoice_id = serializers.IntegerField()
    
    def validate_invoice_id(self, value):
        """Validate invoice exists"""
        try:
            Invoice.objects.get(id=value)
            return value
        except Invoice.DoesNotExist:
            raise serializers.ValidationError("Invoice not found")


class ReturnItemSerializer(serializers.ModelSerializer):
    """Serializer for items in RMA"""
    
    product_name = serializers.CharField(source='order_item.product.name', read_only=True)
    sku = serializers.CharField(source='order_item.product.sku', read_only=True)
    
    class Meta:
        model = ReturnItem
        fields = [
            'id',
            'order_item',
            'product_name',
            'sku',
            'quantity_returned',
            'condition',
            'refund_amount',
            'status',
        ]
        read_only_fields = ['id', 'product_name', 'sku']


class RMASerializer(serializers.ModelSerializer):
    """Serializer for Return Merchandise Authorization (RMA)"""
    
    items = ReturnItemSerializer(many=True, read_only=True)
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    customer_name = serializers.CharField(source='order.customer_name', read_only=True)
    customer_email = serializers.CharField(source='order.customer_email', read_only=True)
    exchange_product_name = serializers.CharField(
        source='exchange_product.name',
        read_only=True,
        allow_null=True,
    )
    
    class Meta:
        model = RMA
        fields = [
            'id',
            'rma_number',
            'order_id',
            'customer_name',
            'customer_email',
            'reason',
            'reason_description',
            'status',
            'is_exchange',
            'exchange_product',
            'exchange_product_name',
            'return_tracking_number',
            'return_carrier',
            'requested_at',
            'approved_at',
            'received_at',
            'completed_at',
            'items',
        ]
        read_only_fields = [
            'id',
            'rma_number',
            'order_id',
            'customer_name',
            'customer_email',
            'requested_at',
            'approved_at',
            'received_at',
            'completed_at',
        ]


class RMACreateSerializer(serializers.Serializer):
    """Serializer for creating RMA"""
    
    order_id = serializers.IntegerField()
    reason = serializers.ChoiceField(
        choices=[
            'defective',
            'not_as_described',
            'changed_mind',
            'damaged_in_shipping',
            'other',
        ]
    )
    reason_description = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of items to return: [{'order_item_id': int, 'quantity': int}]",
    )
    is_exchange = serializers.BooleanField(default=False)
    exchange_product_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate_order_id(self, value):
        """Validate order exists and can be returned"""
        from wasla.apps.orders.models import Order
        try:
            order = Order.objects.get(id=value)
            if order.status not in ['delivered', 'completed', 'returned', 'partially_refunded']:
                raise serializers.ValidationError("Order must be delivered or later status to create RMA")
            return value
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found")
    
    def validate_items(self, value):
        """Validate returned items"""
        if not value:
            raise serializers.ValidationError("At least one item must be returned")
        
        from wasla.apps.orders.models import OrderItem
        for item in value:
            order_item_id = item.get('order_item_id')
            if not order_item_id:
                raise serializers.ValidationError("order_item_id is required for each item")
            
            try:
                OrderItem.objects.get(id=order_item_id)
            except OrderItem.DoesNotExist:
                raise serializers.ValidationError(f"OrderItem {order_item_id} not found")
        
        return value


class RMAApproveSerializer(serializers.Serializer):
    """Serializer for approving RMA"""
    
    comment = serializers.CharField(required=False, allow_blank=True)


class RMATrackingSerializer(serializers.Serializer):
    """Serializer for tracking return shipment"""
    
    carrier = serializers.CharField(max_length=64)
    tracking_number = serializers.CharField(max_length=255)


class RMAInspectionSerializer(serializers.Serializer):
    """Serializer for RMA inspection"""
    
    inspections = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of inspections: [{'return_item_id': int, 'condition': str, 'refund_amount': Decimal}]",
    )


class RefundTransactionSerializer(serializers.ModelSerializer):
    """Serializer for refund transactions"""
    
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    rma_number = serializers.CharField(source='rma.rma_number', read_only=True, allow_null=True)
    
    class Meta:
        model = RefundTransaction
        fields = [
            'id',
            'refund_id',
            'order_id',
            'rma_number',
            'amount',
            'currency',
            'refund_reason',
            'status',
            'created_at',
            'completed_at',
        ]
        read_only_fields = [
            'id',
            'refund_id',
            'order_id',
            'rma_number',
            'created_at',
            'completed_at',
        ]


class RefundRequestSerializer(serializers.Serializer):
    """Serializer for requesting refund"""
    
    order_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    refund_reason = serializers.CharField(max_length=255, required=False, allow_blank=True)
    rma_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate_order_id(self, value):
        """Validate order exists"""
        from wasla.apps.orders.models import Order
        try:
            Order.objects.get(id=value)
            return value
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found")
    
    def validate_amount(self, value):
        """Validate amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value


class StockReservationSerializer(serializers.ModelSerializer):
    """Serializer for stock reservations"""
    
    order_item_id = serializers.IntegerField(source='order_item.id', read_only=True)
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    variant_id = serializers.IntegerField(source='variant.id', read_only=True, allow_null=True)
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = StockReservation
        fields = [
            'id',
            'order_item_id',
            'product_id',
            'product_name',
            'variant_id',
            'quantity',
            'status',
            'created_at',
            'expires_at',
            'released_at',
            'release_reason',
            'is_expired',
        ]
        read_only_fields = [
            'id',
            'order_item_id',
            'product_id',
            'product_name',
            'variant_id',
            'created_at',
            'expires_at',
            'released_at',
        ]
    
    def get_is_expired(self, obj):
        """Check if reservation is expired"""
        return obj.expires_at is not None and obj.expires_at <= timezone.now()


class StockReservationCreateSerializer(serializers.Serializer):
    """Serializer for creating stock reservation"""
    
    order_item_id = serializers.IntegerField()
    quantity = serializers.PositiveIntegerField()
    
    def validate_order_item_id(self, value):
        """Validate order item exists"""
        from wasla.apps.orders.models import OrderItem
        try:
            OrderItem.objects.get(id=value)
            return value
        except OrderItem.DoesNotExist:
            raise serializers.ValidationError("OrderItem not found")
    
    def validate_quantity(self, value):
        """Validate quantity is positive"""
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value

"""
Django admin registrations for production commerce models

Admin interfaces for:
- Invoice management with line items
- RMA workflow and return items
- RefundTransaction audit trail
- StockReservation monitoring
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone

from wasla.apps.orders.models import (
    Invoice,
    InvoiceLineItem,
    RMA,
    ReturnItem,
    RefundTransaction,
    StockReservation,
)
from wasla.apps.orders.services.invoice_service import InvoiceService
from wasla.apps.orders.services.returns_service import ReturnsService


class InvoiceLineItemInline(admin.TabularInline):
    """Inline admin for invoice line items"""
    model = InvoiceLineItem
    extra = 0
    fields = ['description', 'sku', 'quantity', 'unit_price', 'line_subtotal', 'line_tax', 'line_total']
    readonly_fields = ['line_subtotal', 'line_tax', 'line_total']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Admin for invoices"""
    
    list_display = [
        'invoice_number',
        'buyer_name',
        'total_amount',
        'status_badge',
        'issue_date',
        'zatca_status',
    ]
    list_filter = ['status', 'issue_date', 'store_id', 'currency']
    search_fields = ['invoice_number', 'buyer_name', 'buyer_email']
    readonly_fields = [
        'invoice_number',
        'created_at',
        'issued_at',
        'paid_at',
        'zatca_qr_code_display',
        'zatca_hash',
        'zatca_uuid',
    ]
    fieldsets = (
        ('Invoice Info', {
            'fields': ('invoice_number', 'order', 'status', 'issue_date', 'due_date', 'currency'),
        }),
        ('Amounts', {
            'fields': ('subtotal', 'tax_rate', 'tax_amount', 'discount_amount', 'shipping_cost', 'total_amount'),
        }),
        ('Customer', {
            'fields': ('buyer_name', 'buyer_email', 'buyer_vat_id'),
        }),
        ('Seller', {
            'fields': ('seller_name', 'seller_vat_id', 'seller_address', 'seller_bank_details'),
        }),
        ('ZATCA Compliance (Saudi Arabia)', {
            'fields': ('zatca_signed', 'zatca_uuid', 'zatca_hash', 'zatca_qr_code_display'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'issued_at', 'paid_at'),
            'classes': ('collapse',),
        }),
        ('PDF', {
            'fields': ('pdf_file',),
            'classes': ('collapse',),
        }),
    )
    inlines = [InvoiceLineItemInline]
    actions = ['issue_invoice_action', 'mark_paid_action', 'mark_refunded_action']
    
    def status_badge(self, obj):
        """Display status with color coding"""
        colors = {
            'draft': '#d3d3d3',
            'issued': '#87ceeb',
            'paid': '#90ee90',
            'cancelled': '#ff6b6b',
            'refunded': '#ffa500',
        }
        color = colors.get(obj.status, '#ddd')
        return format_html(
            '<span style="background-color: {}; padding: 3px 10px; border-radius: 3px; color: white;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = 'Status'
    
    def zatca_status(self, obj):
        """Display ZATCA compliance status"""
        if obj.zatca_signed:
            return format_html('<span style="color: green;">✓ ZATCA Signed</span>')
        elif obj.zatca_hash:
            return format_html('<span style="color: orange;">⚠ Issued (Not Signed)</span>')
        else:
            return format_html('<span style="color: red;">✗ Not Issued</span>')
    zatca_status.short_description = 'ZATCA Status'
    
    def zatca_qr_code_display(self, obj):
        """Display ZATCA QR code"""
        if obj.zatca_qr_code:
            return format_html(
                '<img src="{}" width="200" height="200" />',
                obj.zatca_qr_code,
            )
        return 'QR Code not generated'
    zatca_qr_code_display.short_description = 'ZATCA QR Code'
    
    def issue_invoice_action(self, request, queryset):
        """Bulk action to issue invoices"""
        service = InvoiceService()
        count = 0
        
        for invoice in queryset.filter(status='draft'):
            try:
                service.issue_invoice(invoice, previous_hash=None)
                count += 1
            except Exception as e:
                self.message_user(request, f"Error issuing {invoice.invoice_number}: {str(e)}", messages.ERROR)
        
        messages.success(request, f"Issued {count} invoices")
    issue_invoice_action.short_description = "Issue selected invoices"
    
    def mark_paid_action(self, request, queryset):
        """Bulk action to mark invoices as paid"""
        count = queryset.update(status='paid', paid_at=timezone.now())
        messages.success(request, f"Marked {count} invoices as paid")
    mark_paid_action.short_description = "Mark as paid"
    
    def mark_refunded_action(self, request, queryset):
        """Bulk action to mark invoices as refunded"""
        count = queryset.update(status='refunded')
        messages.success(request, f"Marked {count} invoices as refunded")
    mark_refunded_action.short_description = "Mark as refunded"
    
    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly after issuance"""
        if obj and obj.status != 'draft':
            return self.readonly_fields + ['subtotal', 'tax_rate', 'discount_amount', 'shipping_cost']
        return self.readonly_fields


class ReturnItemInline(admin.TabularInline):
    """Inline admin for return items in RMA"""
    model = ReturnItem
    extra = 0
    fields = ['order_item', 'quantity_returned', 'condition', 'refund_amount', 'status']
    readonly_fields = ['order_item']


@admin.register(RMA)
class RMAAdmin(admin.ModelAdmin):
    """Admin for Return Merchandise Authorization"""
    
    list_display = [
        'rma_number',
        'order',
        'status_badge',
        'reason',
        'requested_at',
        'item_count',
    ]
    list_filter = ['status', 'reason', 'is_exchange', 'requested_at', 'store_id']
    search_fields = ['rma_number', 'order__customer_email', 'order__customer_name']
    readonly_fields = [
        'rma_number',
        'requested_at',
        'approved_at',
        'received_at',
        'completed_at',
        'order',
    ]
    fieldsets = (
        ('RMA Info', {
            'fields': ('rma_number', 'order', 'status', 'requested_at'),
        }),
        ('Return Details', {
            'fields': ('reason', 'reason_description', 'is_exchange', 'exchange_product'),
        }),
        ('Return Shipment', {
            'fields': ('return_carrier', 'return_tracking_number'),
        }),
        ('Timeline', {
            'fields': ('approved_at', 'received_at', 'completed_at'),
            'classes': ('collapse',),
        }),
    )
    inlines = [ReturnItemInline]
    actions = ['approve_rma_action', 'reject_rma_action', 'mark_received_action']
    
    def status_badge(self, obj):
        """Display status with color coding"""
        colors = {
            'requested': '#d3d3d3',
            'approved': '#87ceeb',
            'rejected': '#ff6b6b',
            'in_transit': '#ffa500',
            'received': '#dda0dd',
            'inspected': '#f0e68c',
            'completed': '#90ee90',
            'cancelled': '#696969',
        }
        color = colors.get(obj.status, '#ddd')
        return format_html(
            '<span style="background-color: {}; padding: 3px 10px; border-radius: 3px; color: white;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = 'Status'
    
    def item_count(self, obj):
        """Display number of items in RMA"""
        return obj.items.count()
    item_count.short_description = 'Items'
    
    def approve_rma_action(self, request, queryset):
        """Bulk action to approve RMAs"""
        service = ReturnsService()
        count = 0
        
        for rma in queryset.filter(status='requested'):
            try:
                service.approve_rma(rma)
                count += 1
            except Exception as e:
                self.message_user(request, f"Error approving {rma.rma_number}: {str(e)}", messages.ERROR)
        
        messages.success(request, f"Approved {count} RMAs")
    approve_rma_action.short_description = "Approve selected RMAs"
    
    def reject_rma_action(self, request, queryset):
        """Bulk action to reject RMAs"""
        service = ReturnsService()
        count = 0
        
        for rma in queryset.filter(status='requested'):
            try:
                service.reject_rma(rma, reason="Rejected by admin")
                count += 1
            except Exception as e:
                self.message_user(request, f"Error rejecting {rma.rma_number}: {str(e)}", messages.ERROR)
        
        messages.success(request, f"Rejected {count} RMAs")
    reject_rma_action.short_description = "Reject selected RMAs"
    
    def mark_received_action(self, request, queryset):
        """Bulk action to mark RMAs as received"""
        service = ReturnsService()
        count = 0
        
        for rma in queryset.filter(status='in_transit'):
            try:
                service.receive_return(rma)
                count += 1
            except Exception as e:
                self.message_user(request, f"Error marking {rma.rma_number} as received: {str(e)}", messages.ERROR)
        
        messages.success(request, f"Marked {count} RMAs as received")
    mark_received_action.short_description = "Mark as received"


@admin.register(ReturnItem)
class ReturnItemAdmin(admin.ModelAdmin):
    """Admin for individual return items"""
    
    list_display = [
        'rma',
        'order_item',
        'quantity_returned',
        'condition',
        'refund_amount',
        'status_badge',
    ]
    list_filter = ['condition', 'status', 'rma__requested_at']
    search_fields = ['rma__rma_number', 'order_item__product__name']
    readonly_fields = ['rma', 'order_item']
    
    def status_badge(self, obj):
        """Display status with color"""
        colors = {
            'pending': '#d3d3d3',
            'approved': '#87ceeb',
            'rejected': '#ff6b6b',
            'refunded': '#90ee90',
        }
        color = colors.get(obj.status, '#ddd')
        return format_html(
            '<span style="background-color: {}; padding: 3px 10px; border-radius: 3px; color: white;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = 'Status'


@admin.register(RefundTransaction)
class RefundTransactionAdmin(admin.ModelAdmin):
    """Admin for refund transactions"""
    
    list_display = [
        'refund_id',
        'order',
        'amount',
        'status_badge',
        'created_at',
        'completed_at',
    ]
    list_filter = ['status', 'created_at', 'store_id']
    search_fields = ['refund_id', 'order__customer_email']
    readonly_fields = [
        'refund_id',
        'order',
        'created_at',
        'completed_at',
        'gateway_response_display',
    ]
    fieldsets = (
        ('Refund Info', {
            'fields': ('refund_id', 'order', 'rma'),
        }),
        ('Amount', {
            'fields': ('amount', 'currency', 'refund_reason'),
        }),
        ('Status', {
            'fields': ('status', 'created_at', 'completed_at'),
        }),
        ('Gateway Response', {
            'fields': ('gateway_response_display',),
            'classes': ('collapse',),
        }),
    )
    actions = ['retry_failed_refunds']
    
    def status_badge(self, obj):
        """Display status with color"""
        colors = {
            'initiated': '#d3d3d3',
            'processing': '#ffa500',
            'completed': '#90ee90',
            'failed': '#ff6b6b',
            'cancelled': '#696969',
        }
        color = colors.get(obj.status, '#ddd')
        return format_html(
            '<span style="background-color: {}; padding: 3px 10px; border-radius: 3px; color: white;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = 'Status'
    
    def gateway_response_display(self, obj):
        """Display gateway response as formatted JSON"""
        import json
        if obj.gateway_response:
            return format_html(
                '<pre>{}</pre>',
                json.dumps(obj.gateway_response, indent=2),
            )
        return 'No response yet'
    gateway_response_display.short_description = 'Gateway Response'
    
    def retry_failed_refunds(self, request, queryset):
        """Bulk action to retry failed refunds"""
        from wasla.apps.orders.tasks import process_refund
        
        failed = queryset.filter(status__in=['failed', 'initiated'])
        count = 0
        
        for refund in failed:
            process_refund.delay(refund.id)
            count += 1
        
        messages.success(request, f"Queued {count} refunds for retry")
    retry_failed_refunds.short_description = "Retry failed refunds"


@admin.register(StockReservation)
class StockReservationAdmin(admin.ModelAdmin):
    """Admin for stock reservations"""
    
    list_display = [
        'order_item',
        'reserved_quantity',
        'status_badge',
        'expires_at',
        'is_expired_indicator',
    ]
    list_filter = ['status', 'expires_at', 'created_at', 'store_id']
    search_fields = ['order_item__product__name', 'inventory__product__sku']
    readonly_fields = [
        'order_item',
        'inventory',
        'created_at',
        'released_at',
        'expiry_info',
    ]
    fieldsets = (
        ('Reservation Info', {
            'fields': ('order_item', 'inventory', 'reserved_quantity'),
        }),
        ('Status', {
            'fields': ('status', 'expiry_info'),
        }),
        ('Dates', {
            'fields': ('expires_at', 'created_at', 'released_at'),
        }),
        ('Release Info', {
            'fields': ('release_reason',),
            'classes': ('collapse',),
        }),
    )
    actions = ['release_expired_action', 'extend_ttl_action']
    
    def status_badge(self, obj):
        """Display status with color"""
        colors = {
            'reserved': '#d3d3d3',
            'confirmed': '#87ceeb',
            'released': '#90ee90',
            'expired': '#ff6b6b',
        }
        color = colors.get(obj.status, '#ddd')
        return format_html(
            '<span style="background-color: {}; padding: 3px 10px; border-radius: 3px; color: white;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = 'Status'
    
    def is_expired_indicator(self, obj):
        """Show if reservation is expired"""
        if obj.is_expired():
            return format_html('<span style="color: red;">EXPIRED</span>')
        
        from django.utils import timezone
        time_left = (obj.expires_at - timezone.now()).total_seconds() / 60
        
        if time_left < 5:
            return format_html('<span style="color: orange;">{:.0f} min</span>', time_left)
        else:
            return format_html('<span style="color: green;">{:.0f} min</span>', time_left)
    is_expired_indicator.short_description = 'Time Left'
    
    def expiry_info(self, obj):
        """Display detailed expiry info"""
        from django.utils import timezone
        
        if obj.is_expired():
            return format_html('<span style="color: red;">EXPIRED</span>')
        
        time_left = obj.expires_at - timezone.now()
        minutes = int(time_left.total_seconds() / 60)
        return f"Expires in {minutes} minutes ({obj.expires_at.strftime('%Y-%m-%d %H:%M:%S')})"
    expiry_info.short_description = 'Expiry Info'
    
    def release_expired_action(self, request, queryset):
        """Bulk action to release expired reservations"""
        from wasla.apps.orders.services.stock_reservation_service import StockReservationService
        
        service = StockReservationService()
        expired = queryset.filter(status__in=['reserved', 'confirmed'], expires_at__lt=timezone.now())
        count = 0
        
        for reservation in expired:
            try:
                service.release_reservation(reservation, reason='admin_manual_release')
                count += 1
            except Exception as e:
                self.message_user(request, f"Error releasing {reservation.id}: {str(e)}", messages.ERROR)
        
        messages.success(request, f"Released {count} expired reservations")
    release_expired_action.short_description = "Release expired reservations"
    
    def extend_ttl_action(self, request, queryset):
        """Bulk action to extend TTL for active reservations"""
        from wasla.apps.orders.services.stock_reservation_service import StockReservationService
        
        service = StockReservationService()
        active = queryset.filter(status__in=['reserved', 'confirmed'])
        count = 0
        
        for reservation in active:
            try:
                service.confirm_reservation(reservation)
                count += 1
            except Exception as e:
                self.message_user(request, f"Error extending {reservation.id}: {str(e)}", messages.ERROR)
        
        messages.success(request, f"Extended TTL for {count} reservations")
    extend_ttl_action.short_description = "Extend TTL to 30 minutes"
    
    class Media:
        css = {'all': ('admin/css/admin_custom.css',)}

"""
Django Admin interfaces for SaaS recurring billing system.

Provides admin views for:
- Subscription management
- Invoice tracking
- Dunning attempt management
- Payment events and webhook debugging
- Billing cycles
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import timedelta

from .models_billing import (
    Subscription,
    Invoice,
    BillingCycle,
    DunningAttempt,
    PaymentEvent,
    PaymentMethod,
    SubscriptionItem,
)
from .services_billing import (
    SubscriptionService,
    DunningService,
)


# Admin Actions

def suspend_subscriptions(modeladmin, request, queryset):
    """Admin action to suspend subscriptions."""
    count = 0
    for sub in queryset:
        if sub.state == 'active':
            SubscriptionService.suspend_subscription(
                sub,
                reason='Admin action'
            )
            count += 1
    modeladmin.message_user(request, f'{count} subscriptions suspended.')
suspend_subscriptions.short_description = 'Suspend selected subscriptions'


def reactivate_subscriptions(modeladmin, request, queryset):
    """Admin action to reactivate suspended subscriptions."""
    count = 0
    for sub in queryset:
        if sub.state in ['suspended', 'grace']:
            SubscriptionService.reactivate_subscription(sub)
            count += 1
    modeladmin.message_user(request, f'{count} subscriptions reactivated.')
reactivate_subscriptions.short_description = 'Reactivate selected subscriptions'


def mark_invoices_as_paid(modeladmin, request, queryset):
    """Admin action to mark invoices as paid (for manual adjustments)."""
    count = 0
    for invoice in queryset:
        if invoice.status != 'paid':
            invoice.amount_paid = invoice.total
            invoice.amount_due = 0
            invoice.status = 'paid'
            invoice.paid_date = timezone.now().date()
            invoice.save()
            count += 1
    modeladmin.message_user(request, f'{count} invoices marked as paid.')
mark_invoices_as_paid.short_description = 'Mark selected invoices as paid'


def retry_dunning_attempts(modeladmin, request, queryset):
    """Admin action to manually retry failed dunning attempts."""
    count = 0
    for attempt in queryset:
        if attempt.status in ['failed', 'pending']:
            attempt.status = 'pending'
            attempt.scheduled_for = timezone.now()
            attempt.error_message = ''
            attempt.save()
            count += 1
    modeladmin.message_user(request, f'{count} dunning attempts queued for retry.')
retry_dunning_attempts.short_description = 'Retry selected dunning attempts'


# Inline Admin Classes

class SubscriptionItemInline(admin.TabularInline):
    """Inline view for subscription items."""
    model = SubscriptionItem
    fields = ('name', 'billing_type', 'price', 'current_usage', 'usage_limit', 'created_at')
    readonly_fields = ('created_at',)
    extra = 0


class BillingCycleInline(admin.TabularInline):
    """Inline view for billing cycles."""
    model = BillingCycle
    fields = ('period_start', 'period_end', 'status', 'total', 'invoice_date')
    readonly_fields = ('period_start', 'period_end', 'invoice_date')
    extra = 0
    can_delete = False


class PaymentMethodInline(admin.StackedInline):
    """Inline view for payment methods."""
    model = PaymentMethod
    fields = ('method_type', 'display_name', 'status', 'added_at', 'expires_at', 'last_used_at')
    readonly_fields = ('added_at', 'last_used_at')
    extra = 0


class DunningAttemptInline(admin.TabularInline):
    """Inline view for dunning attempts."""
    model = DunningAttempt
    fields = ('attempt_number', 'status', 'scheduled_for', 'attempted_at', 'next_retry_at', 'error_code')
    readonly_fields = ('attempted_at', 'error_code')
    extra = 0
    can_delete = False


class InvoiceInline(admin.TabularInline):
    """Inline view for invoices."""
    model = Invoice
    fields = ('number', 'status', 'total', 'amount_paid', 'amount_due', 'due_date')
    readonly_fields = ('number', 'status', 'due_date')
    extra = 0
    can_delete = False


# ModelAdmin Classes

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Admin interface for subscription management."""
    
    list_display = (
        'id_display',
        'tenant_name',
        'plan_name',
        'state_badge',
        'next_billing_date',
        'status_actions',
        'created_at',
    )
    
    list_filter = (
        'state',
        'created_at',
        'next_billing_date',
        ('grace_until', admin.EmptyFieldListFilter),
        ('suspension_reason', admin.EmptyFieldListFilter),
    )
    
    search_fields = (
        'tenant__name',
        'tenant__slug',
        'plan__name',
        'id',
    )
    
    readonly_fields = (
        'id',
        'started_at',
        'cancelled_at',
        'suspended_at',
        'created_at',
        'updated_at',
        'subscription_info',
        'billing_status',
    )
    
    fieldsets = (
        ('Subscription Info', {
            'fields': ('id', 'tenant', 'plan', 'subscription_info')
        }),
        ('Billing', {
            'fields': (
                'state',
                'next_billing_date',
                'billing_cycle_anchor',
                'currency',
                'billing_status',
            )
        }),
        ('Grace Period', {
            'fields': ('grace_until',),
            'classes': ('collapse',),
        }),
        ('Suspension', {
            'fields': ('suspended_at', 'suspension_reason'),
            'classes': ('collapse',),
        }),
        ('Cancellation', {
            'fields': ('cancelled_at', 'cancellation_reason'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('started_at', 'created_at', 'updated_at'),
        }),
    )
    
    inlines = (
        SubscriptionItemInline,
        PaymentMethodInline,
        BillingCycleInline,
        InvoiceInline,
        DunningAttemptInline,
    )
    
    actions = (
        suspend_subscriptions,
        reactivate_subscriptions,
    )
    
    def id_display(self, obj):
        """Display subscription ID."""
        return str(obj.id)[:8] + '...'
    id_display.short_description = 'ID'
    
    def tenant_name(self, obj):
        """Display tenant name."""
        return obj.tenant.name
    tenant_name.short_description = 'Tenant'
    
    def plan_name(self, obj):
        """Display plan name."""
        return obj.plan.name
    plan_name.short_description = 'Plan'
    
    def state_badge(self, obj):
        """Display state as colored badge."""
        colors = {
            'active': '#28a745',  # Green
            'past_due': '#ffc107',  # Yellow
            'grace': '#17a2b8',  # Blue
            'suspended': '#dc3545',  # Red
            'cancelled': '#6c757d',  # Gray
        }
        color = colors.get(obj.state, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_state_display()
        )
    state_badge.short_description = 'State'
    
    def status_actions(self, obj):
        """Display action buttons."""
        buttons = []
        if obj.state == 'active':
            buttons.append(f'<a class="button" href="#" onclick="return false;">Suspend</a>')
        elif obj.state in ['suspended', 'grace']:
            buttons.append(f'<a class="button" href="#" onclick="return false;">Reactivate</a>')
        
        if obj.state != 'cancelled':
            buttons.append(f'<a class="button" href="#" onclick="return false;">Cancel</a>')
        
        return format_html(' '.join(buttons)) if buttons else '-'
    status_actions.short_description = 'Actions'
    
    def subscription_info(self, obj):
        """Display subscription info summary."""
        overdue_days = 0
        if obj.state == 'past_due':
            overdue_days = (timezone.now().date() - obj.next_billing_date).days
        
        info = f"""
        <strong>State:</strong> {obj.get_state_display()}<br>
        <strong>Plan:</strong> {obj.plan.name}<br>
        <strong>Tenant:</strong> {obj.tenant.name}<br>
        <strong>Active Since:</strong> {obj.started_at.strftime('%Y-%m-%d %H:%M') if obj.started_at else 'N/A'}<br>
        """
        
        if obj.state == 'past_due':
            info += f"<strong>Overdue Since:</strong> {overdue_days} days<br>"
        
        if obj.grace_until:
            days_remaining = (obj.grace_until.date() - timezone.now().date()).days
            info += f"<strong>Grace Period Expires:</strong> {days_remaining} days<br>"
        
        return format_html(info)
    subscription_info.short_description = 'Subscription Info'
    
    def billing_status(self, obj):
        """Display billing status."""
        # Get outstanding invoices
        outstanding = Invoice.objects.filter(
            subscription=obj,
            status__in=['issued', 'overdue', 'partial']
        ).aggregate(total=Sum('amount_due'))['total'] or 0
        
        status_html = f"""
        <strong>Next Billing Date:</strong> {obj.next_billing_date}<br>
        <strong>Outstanding Balance:</strong> {obj.currency} {outstanding:.2f}<br>
        """
        
        # Recent invoices
        recent = Invoice.objects.filter(subscription=obj).order_by('-issued_date')[:3]
        if recent:
            status_html += "<strong>Recent Invoices:</strong><br><ul>"
            for inv in recent:
                status_html += f"""
                <li>{inv.number} - {inv.status} - 
                    Due: {inv.due_date} - 
                    {inv.currency} {inv.amount_due:.2f} due
                </li>
                """
            status_html += "</ul>"
        
        return format_html(status_html)
    billing_status.short_description = 'Billing Status'


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Admin interface for invoice management."""
    
    list_display = (
        'number',
        'subscription_tenant',
        'status_badge',
        'issued_date',
        'due_date',
        'total_amount',
        'amount_due_display',
        'is_overdue',
    )
    
    list_filter = (
        'status',
        'issued_date',
        'due_date',
        ('billing_cycle__subscription__state', 'State'),
    )
    
    search_fields = (
        'number',
        'subscription__tenant__name',
        'subscription__plan__name',
    )
    
    readonly_fields = (
        'number',
        'id',
        'issued_date',
        'idempotency_key',
        'created_at',
        'updated_at',
        'invoice_details',
    )
    
    fieldsets = (
        ('Invoice Info', {
            'fields': ('id', 'number', 'idempotency_key', 'subscription')
        }),
        ('Billing Cycle', {
            'fields': ('billing_cycle',)
        }),
        ('Amounts', {
            'fields': (
                'subtotal',
                'discount',
                'tax',
                'total',
                'amount_paid',
                'amount_due',
            )
        }),
        ('Status & Dates', {
            'fields': (
                'status',
                'issued_date',
                'due_date',
                'paid_date',
                'invoice_details',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    actions = (
        mark_invoices_as_paid,
    )
    
    def subscription_tenant(self, obj):
        """Display subscription tenant name."""
        return obj.subscription.tenant.name
    subscription_tenant.short_description = 'Tenant'
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'draft': '#6c757d',
            'issued': '#0069d9',
            'overdue': '#dc3545',
            'partial': '#ffc107',
            'paid': '#28a745',
            'void': '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def total_amount(self, obj):
        """Display total amount."""
        return f"{obj.subscription.currency} {obj.total:.2f}"
    total_amount.short_description = 'Total'
    
    def amount_due_display(self, obj):
        """Display amount due."""
        if obj.amount_due > 0:
            return format_html(
                '<span style="color: red; font-weight: bold;">{} {:.2f}</span>',
                obj.subscription.currency,
                obj.amount_due
            )
        return f"{obj.subscription.currency} 0.00"
    amount_due_display.short_description = 'Due'
    
    def is_overdue(self, obj):
        """Check if invoice is overdue."""
        if obj.status in ['paid', 'void']:
            return '-'
        if obj.due_date < timezone.now().date():
            days = (timezone.now().date() - obj.due_date).days
            return format_html(
                '<span style="color: red; font-weight: bold;">Yes ({} days)</span>',
                days
            )
        return 'No'
    is_overdue.short_description = 'Overdue?'
    
    def invoice_details(self, obj):
        """Display invoice details."""
        dunning_attempts = DunningAttempt.objects.filter(invoice=obj).count()
        
        details = f"""
        <strong>Cycle Period:</strong> {obj.billing_cycle.period_start} to {obj.billing_cycle.period_end}<br>
        <strong>Days to Due:</strong> {(obj.due_date - timezone.now().date()).days} days<br>
        <strong>Dunning Attempts:</strong> {dunning_attempts}<br>
        <strong>Payment Status:</strong> {obj.amount_paid}/{obj.total} {obj.subscription.currency} paid<br>
        """
        
        if obj.paid_date:
            details += f"<strong>Paid On:</strong> {obj.paid_date}<br>"
        
        return format_html(details)
    invoice_details.short_description = 'Invoice Details'


@admin.register(BillingCycle)
class BillingCycleAdmin(admin.ModelAdmin):
    """Admin interface for billing cycle management."""
    
    list_display = (
        'subscription_display',
        'period_start',
        'period_end',
        'status_badge',
        'total_amount',
        'invoice_link',
    )
    
    list_filter = (
        'status',
        'period_start',
        'period_end',
    )
    
    search_fields = (
        'subscription__tenant__name',
        'subscription__plan__name',
    )
    
    readonly_fields = (
        'id',
        'subscription',
        'created_at',
        'updated_at',
        'cycle_details',
    )
    
    fieldsets = (
        ('Billing Period', {
            'fields': ('subscription', 'period_start', 'period_end')
        }),
        ('Amounts', {
            'fields': (
                'subtotal',
                'discount',
                'tax',
                'total',
                'proration_total',
                'proration_reason',
            )
        }),
        ('Dates', {
            'fields': ('invoice_date', 'due_date', 'status')
        }),
        ('Details', {
            'fields': ('cycle_details',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    def subscription_display(self, obj):
        """Display subscription with tenant."""
        return f"{obj.subscription.tenant.name} - {obj.subscription.plan.name}"
    subscription_display.short_description = 'Subscription'
    
    def status_badge(self, obj):
        """Display status as badge."""
        colors = {
            'pending': '#6c757d',
            'billed': '#0069d9',
            'partial': '#ffc107',
            'paid': '#28a745',
            'failed': '#dc3545',
            'cancelled': '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def total_amount(self, obj):
        """Display total."""
        return f"{obj.subscription.currency} {obj.total:.2f}"
    total_amount.short_description = 'Total'
    
    def invoice_link(self, obj):
        """Link to invoice if exists."""
        try:
            invoice = obj.invoice
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:subscriptions_invoice_change', args=[invoice.id]),
                invoice.number
            )
        except:
            return '-'
    invoice_link.short_description = 'Invoice'
    
    def cycle_details(self, obj):
        """Display cycle details."""
        items = SubscriptionItem.objects.filter(subscription=obj.subscription)
        
        details = f"""
        <strong>Items:</strong> {items.count()}<br>
        <strong>Subtotal:</strong> {obj.subscription.currency} {obj.subtotal:.2f}<br>
        <strong>Tax (15%):</strong> {obj.subscription.currency} {obj.tax:.2f}<br>
        <strong>Discount:</strong> {obj.subscription.currency} {obj.discount:.2f}<br>
        """
        
        if obj.proration_total != 0:
            details += f"<strong>Proration ({obj.proration_reason}):</strong> {obj.subscription.currency} {obj.proration_total:.2f}<br>"
        
        return format_html(details)
    cycle_details.short_description = 'Cycle Details'


@admin.register(DunningAttempt)
class DunningAttemptAdmin(admin.ModelAdmin):
    """Admin interface for dunning attempt management."""
    
    list_display = (
        'attempt_number_display',
        'subscription_display',
        'status_badge',
        'scheduled_for',
        'attempted_at',
        'next_retry_at',
        'actions_display',
    )
    
    list_filter = (
        'status',
        'strategy',
        'created_at',
        'scheduled_for',
    )
    
    search_fields = (
        'invoice__number',
        'subscription__tenant__name',
        'error_code',
    )
    
    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
        'dunning_details',
    )
    
    fieldsets = (
        ('Invoice & Subscription', {
            'fields': ('invoice', 'subscription')
        }),
        ('Attempt Details', {
            'fields': (
                'attempt_number',
                'strategy',
                'status',
                'dunning_details',
            )
        }),
        ('Scheduling', {
            'fields': ('scheduled_for', 'attempted_at', 'next_retry_at')
        }),
        ('Error Info', {
            'fields': ('error_code', 'error_message'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    actions = (
        retry_dunning_attempts,
    )
    
    def attempt_number_display(self, obj):
        """Display attempt number."""
        return f"Attempt {obj.attempt_number}"
    attempt_number_display.short_description = 'Attempt'
    
    def subscription_display(self, obj):
        """Display subscription."""
        return f"{obj.subscription.tenant.name}"
    subscription_display.short_description = 'Tenant'
    
    def status_badge(self, obj):
        """Display status badge."""
        colors = {
            'pending': '#ffc107',
            'in_progress': '#0069d9',
            'success': '#28a745',
            'failed': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def actions_display(self, obj):
        """Display available actions."""
        if obj.status in ['failed', 'pending']:
            return format_html('<a class="button" href="#" onclick="return false;">Retry</a>')
        return '-'
    actions_display.short_description = 'Actions'
    
    def dunning_details(self, obj):
        """Display dunning details."""
        details = f"""
        <strong>Invoice:</strong> {obj.invoice.number}<br>
        <strong>Amount Due:</strong> {obj.invoice.subscription.currency} {obj.invoice.amount_due:.2f}<br>
        <strong>Strategy:</strong> {obj.get_strategy_display()}<br>
        <strong>Scheduled For:</strong> {obj.scheduled_for}<br>
        """
        
        if obj.attempted_at:
            details += f"<strong>Attempted At:</strong> {obj.attempted_at}<br>"
        
        if obj.status == 'failed' and obj.error_code:
            details += f"<strong>Error:</strong> {obj.error_code}<br>"
        
        if obj.next_retry_at:
            days_until = (obj.next_retry_at.date() - timezone.now().date()).days
            details += f"<strong>Next Retry:</strong> {obj.next_retry_at} ({days_until} days from now)<br>"
        
        return format_html(details)
    dunning_details.short_description = 'Dunning Details'


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    """Admin interface for payment event management (webhook debugging)."""
    
    list_display = (
        'provider_event_id_short',
        'event_type_display',
        'status_badge',
        'subscription_link',
        'created_at',
        'processed_at',
    )
    
    list_filter = (
        'event_type',
        'status',
        'created_at',
    )
    
    search_fields = (
        'provider_event_id',
        'subscription__tenant__name',
        'invoice__number',
    )
    
    readonly_fields = (
        'id',
        'provider_event_id',
        'event_type',
        'created_at',
        'payload_display',
        'event_details',
    )
    
    fieldsets = (
        ('Event Info', {
            'fields': ('id', 'provider_event_id', 'event_type', 'status')
        }),
        ('References', {
            'fields': ('subscription', 'invoice')
        }),
        ('Event Data', {
            'fields': ('payload_display',)
        }),
        ('Processing', {
            'fields': ('processed_at', 'error_message', 'event_details'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
        }),
    )
    
    def provider_event_id_short(self, obj):
        """Display shortened provider event ID."""
        return str(obj.provider_event_id)[:20] + '...'
    provider_event_id_short.short_description = 'Provider Event ID'
    
    def event_type_display(self, obj):
        """Display event type."""
        return obj.get_event_type_display()
    event_type_display.short_description = 'Event Type'
    
    def status_badge(self, obj):
        """Display status badge."""
        colors = {
            'received': '#0069d9',
            'processing': '#ffc107',
            'processed': '#28a745',
            'failed': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def subscription_link(self, obj):
        """Link to subscription if exists."""
        if obj.subscription:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:subscriptions_subscription_change', args=[obj.subscription.id]),
                f"{obj.subscription.tenant.name}"
            )
        return '-'
    subscription_link.short_description = 'Subscription'
    
    def payload_display(self, obj):
        """Display event payload."""
        import json
        payload_json = json.dumps(obj.payload, indent=2)
        return format_html(
            '<pre style="background-color: #f5f5f5; padding: 10px; border-radius: 3px; overflow-x: auto;">{}</pre>',
            payload_json
        )
    payload_display.short_description = 'Event Payload'
    
    def event_details(self, obj):
        """Display event details."""
        details = f"""
        <strong>Status:</strong> {obj.get_status_display()}<br>
        <strong>Created:</strong> {obj.created_at}<br>
        """
        
        if obj.processed_at:
            details += f"<strong>Processed:</strong> {obj.processed_at}<br>"
        
        if obj.status == 'failed':
            details += f"<strong>Error:</strong> {obj.error_message}<br>"
        
        return format_html(details)
    event_details.short_description = 'Event Details'


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    """Admin interface for payment method management."""
    
    list_display = (
        'display_name',
        'subscription_display',
        'method_type_display',
        'status_badge',
        'added_at',
        'last_used_at',
    )
    
    list_filter = (
        'method_type',
        'status',
        'added_at',
    )
    
    search_fields = (
        'display_name',
        'subscription__tenant__name',
        'provider_customer_id',
    )
    
    readonly_fields = (
        'id',
        'subscription',
        'provider_customer_id',
        'provider_payment_method_id',
        'added_at',
        'last_used_at',
        'created_at',
        'updated_at',
    )
    
    fieldsets = (
        ('Payment Method', {
            'fields': ('id', 'display_name', 'subscription', 'method_type', 'status')
        }),
        ('Provider Info', {
            'fields': ('provider_customer_id', 'provider_payment_method_id'),
            'classes': ('collapse',),
        }),
        ('Usage', {
            'fields': ('added_at', 'last_used_at', 'expires_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    def subscription_display(self, obj):
        """Display subscription."""
        return f"{obj.subscription.tenant.name}"
    subscription_display.short_description = 'Tenant'
    
    def method_type_display(self, obj):
        """Display method type."""
        return obj.get_method_type_display()
    method_type_display.short_description = 'Method Type'
    
    def status_badge(self, obj):
        """Display status badge."""
        colors = {
            'active': '#28a745',
            'inactive': '#6c757d',
            'expired': '#dc3545',
            'invalid': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

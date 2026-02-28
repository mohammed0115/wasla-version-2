from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.views.generic import ListView, DetailView, TemplateView
from django.views.generic.edit import FormView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.utils import timezone
from django.core.paginator import Paginator

from .models_billing import (
    Subscription, Invoice, BillingCycle, PaymentMethod, 
    DunningAttempt, BillingPlan, SubscriptionItem
)
from .services_billing import SubscriptionService, BillingService, DunningService
from .forms import PaymentMethodForm, PlanChangeForm


# ============================================================================
# Dashboard View
# ============================================================================

@login_required
def billing_dashboard(request):
    """
    Main billing overview dashboard for customers.
    Shows subscription status, outstanding balance, recent invoices, and billing history.
    """
    try:
        subscription = Subscription.objects.get(
            user=request.user, 
            tenant=request.user.tenant
        )
    except Subscription.DoesNotExist:
        # No subscription found
        return render(request, 'subscriptions/no_subscription.html')

    # Get outstanding invoices
    outstanding_invoices = Invoice.objects.filter(
        billing_cycle__subscription=subscription,
        status__in=['issued', 'overdue', 'partial']
    ).order_by('-issued_date')

    # Get recent invoices (5 most recent)
    recent_invoices = Invoice.objects.filter(
        billing_cycle__subscription=subscription
    ).order_by('-issued_date')[:5]

    # Get billing cycles history
    billing_cycles = BillingCycle.objects.filter(
        subscription=subscription
    ).order_by('-period_end')[:10]

    # Calculate totals
    outstanding_balance = sum(
        inv.amount_due for inv in outstanding_invoices
    )
    days_until_billing = (
        subscription.next_billing_date - timezone.now().date()
    ).days if subscription.next_billing_date else None

    context = {
        'subscription': subscription,
        'outstanding_balance': outstanding_balance,
        'outstanding_invoices': outstanding_invoices,
        'recent_invoices': recent_invoices,
        'billing_cycles': billing_cycles,
        'days_until_billing': days_until_billing,
        'payment_method': subscription.payment_method,
    }

    return render(request, 'subscriptions/dashboard.html', context)


# ============================================================================
# Subscription Detail View
# ============================================================================

@login_required
def subscription_detail(request, subscription_id=None):
    """
    Detailed subscription management page.
    Shows plan details, subscription items, and allows plan changes and cancellations.
    """
    if subscription_id:
        subscription = get_object_or_404(
            Subscription, 
            id=subscription_id,
            user=request.user,
            tenant=request.user.tenant
        )
    else:
        try:
            subscription = Subscription.objects.get(
                user=request.user,
                tenant=request.user.tenant
            )
        except Subscription.DoesNotExist:
            messages.error(request, 'No active subscription found.')
            return redirect('subscriptions:dashboard')

    # Get subscription items
    items = SubscriptionItem.objects.filter(subscription=subscription)

    # Get payment method
    payment_method = subscription.payment_method

    context = {
        'subscription': subscription,
        'items': items,
        'payment_method': payment_method,
        'plan_features': subscription.plan.features if hasattr(subscription.plan, 'features') else [],
    }

    # Handle POST requests for cancel or grace period
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'cancel':
            reason = request.POST.get('cancel_reason', '')
            service = SubscriptionService()
            try:
                service.cancel_subscription(subscription, reason=reason)
                messages.success(
                    request, 
                    'Your subscription has been cancelled. '
                    'You will still have access until the end of your billing period.'
                )
                return redirect('subscriptions:subscription-detail', subscription_id=subscription.id)
            except Exception as e:
                messages.error(request, f'Error cancelling subscription: {str(e)}')

        elif action == 'grace_period':
            requested_days = request.POST.get('grace_days', 7)
            service = SubscriptionService()
            try:
                service.add_grace_period(subscription, days=int(requested_days))
                messages.success(
                    request,
                    f'Grace period extended. You have {requested_days} more days to pay.'
                )
                return redirect('subscriptions:subscription-detail', subscription_id=subscription.id)
            except Exception as e:
                messages.error(request, f'Error extending grace period: {str(e)}')

    return render(request, 'subscriptions/subscription_detail.html', context)


# ============================================================================
# Invoice Views
# ============================================================================

@login_required
def invoice_list(request):
    """
    Invoice listing page with filtering by status and pagination.
    """
    try:
        subscription = Subscription.objects.get(
            user=request.user,
            tenant=request.user.tenant
        )
    except Subscription.DoesNotExist:
        messages.error(request, 'No active subscription found.')
        return redirect('subscriptions:dashboard')

    # Get invoices
    invoices = Invoice.objects.filter(
        billing_cycle__subscription=subscription
    ).order_by('-issued_date')

    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'all':
        invoices = invoices.filter(status=status_filter)

    # Filter for overdue only
    if request.GET.get('overdue_only'):
        invoices = invoices.filter(status='overdue')

    # Pagination
    paginator = Paginator(invoices, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'invoices': page_obj.object_list,
        'status_filter': status_filter,
        'overdue_only': request.GET.get('overdue_only', False),
    }

    return render(request, 'subscriptions/invoice_list.html', context)


@login_required
def invoice_detail(request, invoice_id):
    """
    Detailed invoice view with breakdown, payment options, and dunning history.
    """
    invoice = get_object_or_404(Invoice, id=invoice_id)

    # Verify ownership
    if invoice.billing_cycle.subscription.user != request.user:
        return HttpResponseForbidden('You do not have access to this invoice.')

    if invoice.billing_cycle.subscription.tenant != request.user.tenant:
        return HttpResponseForbidden('You do not have access to this invoice.')

    # Get dunning attempts
    dunning_attempts = DunningAttempt.objects.filter(
        subscription=invoice.billing_cycle.subscription,
        invoice=invoice
    ).order_by('-created_at')

    context = {
        'invoice': invoice,
        'dunning_attempts': dunning_attempts,
        'payment_url': request.build_absolute_uri('/billing/pay/'),
        'manage_subscription_url': request.build_absolute_uri('/billing/subscription/'),
    }

    return render(request, 'subscriptions/invoice_detail.html', context)


# ============================================================================
# Payment Method Views
# ============================================================================

@login_required
def payment_method(request):
    """
    Payment method management page.
    Shows current payment method and form to update/add new one.
    """
    try:
        subscription = Subscription.objects.get(
            user=request.user,
            tenant=request.user.tenant
        )
    except Subscription.DoesNotExist:
        messages.error(request, 'No active subscription found.')
        return redirect('subscriptions:dashboard')

    payment_method = subscription.payment_method

    if request.method == 'POST':
        form = PaymentMethodForm(request.POST)
        if form.is_valid():
            # Create or update payment method
            service = BillingService()
            try:
                pm = service.add_payment_method(
                    subscription=subscription,
                    method_type=form.cleaned_data['method_type'],
                    token=form.cleaned_data.get('token'),
                    provider=form.cleaned_data.get('provider', 'stripe'),
                    display_name=form.cleaned_data.get('display_name'),
                )
                messages.success(request, 'Payment method updated successfully.')
                return redirect('subscriptions:payment-method')
            except Exception as e:
                messages.error(request, f'Error updating payment method: {str(e)}')
    else:
        form = PaymentMethodForm()

    context = {
        'subscription': subscription,
        'payment_method': payment_method,
        'form': form,
    }

    return render(request, 'subscriptions/payment_method.html', context)


# ============================================================================
# Plan Change Views
# ============================================================================

@login_required
def plan_change(request, subscription_id=None):
    """
    Plan change/comparison page.
    Shows available plans and handles plan change requests.
    """
    if subscription_id:
        subscription = get_object_or_404(
            Subscription,
            id=subscription_id,
            user=request.user,
            tenant=request.user.tenant
        )
    else:
        try:
            subscription = Subscription.objects.get(
                user=request.user,
                tenant=request.user.tenant
            )
        except Subscription.DoesNotExist:
            messages.error(request, 'No active subscription found.')
            return redirect('subscriptions:dashboard')

    # Get available plans
    available_plans = BillingPlan.objects.filter(
        is_active=True,
        tenant=request.user.tenant
    ).order_by('price')

    # Prepare comparison features
    comparison_features = [
        {'name': 'Price', 'plans': {p.id: p.price for p in available_plans}},
        {'name': 'Users', 'plans': {p.id: getattr(p, 'max_users', '∞') for p in available_plans}},
        {'name': 'API Calls', 'plans': {p.id: getattr(p, 'api_calls_limit', '∞') for p in available_plans}},
        {'name': 'Support', 'plans': {p.id: getattr(p, 'support_tier', 'Standard') for p in available_plans}},
    ]

    # Handle plan change POST
    if request.method == 'POST':
        new_plan_id = request.POST.get('new_plan_id')
        try:
            new_plan = BillingPlan.objects.get(id=new_plan_id)
            service = SubscriptionService()
            service.change_plan(subscription, new_plan)
            messages.success(
                request,
                f'Your plan has been changed to {new_plan.name}. '
                'The change takes effect immediately.'
            )
            return redirect('subscriptions:subscription-detail', subscription_id=subscription.id)
        except BillingPlan.DoesNotExist:
            messages.error(request, 'Selected plan not found.')
        except Exception as e:
            messages.error(request, f'Error changing plan: {str(e)}')

    context = {
        'subscription': subscription,
        'available_plans': available_plans,
        'comparison_features': comparison_features,
    }

    return render(request, 'subscriptions/plan_change.html', context)


# ============================================================================
# Admin Dashboard Views
# ============================================================================

@login_required
def admin_billing_dashboard(request):
    """
    Admin dashboard showing billing analytics and key metrics.
    Requires admin permissions.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden('Admin access required.')

    # Get all subscriptions
    subscriptions = Subscription.objects.filter(tenant=request.user.tenant)

    # Get key metrics
    total_mrr = sum(sub.plan.price for sub in subscriptions.filter(status='active'))
    active_count = subscriptions.filter(status='active').count()
    overdue_count = subscriptions.filter(status='past_due').count()
    suspended_count = subscriptions.filter(status='suspended').count()

    # Get recent invoices
    recent_invoices = Invoice.objects.filter(
        billing_cycle__subscription__tenant=request.user.tenant
    ).order_by('-issued_date')[:20]

    # Get payment events
    from .models import PaymentEvent
    recent_payments = PaymentEvent.objects.filter(
        subscription__tenant=request.user.tenant,
        status='succeeded'
    ).order_by('-processed_at')[:10]

    context = {
        'total_mrr': total_mrr,
        'active_count': active_count,
        'overdue_count': overdue_count,
        'suspended_count': suspended_count,
        'subscriptions': subscriptions,
        'recent_invoices': recent_invoices,
        'recent_payments': recent_payments,
    }

    return render(request, 'subscriptions/admin_dashboard.html', context)


# ============================================================================
# API/AJAX Views
# ============================================================================

@login_required
def proration_calculator(request):
    """
    AJAX endpoint to calculate proration when changing plans.
    """
    if not request.is_ajax() or request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    try:
        subscription_id = request.POST.get('subscription_id')
        new_plan_id = request.POST.get('new_plan_id')

        subscription = Subscription.objects.get(id=subscription_id)
        new_plan = BillingPlan.objects.get(id=new_plan_id)

        # Calculate proration
        service = BillingService()
        proration = service.calculate_proration(subscription, new_plan)

        return JsonResponse({
            'success': True,
            'current_price': float(subscription.plan.price),
            'new_price': float(new_plan.price),
            'proration_amount': float(proration.get('amount', 0)),
            'proration_type': proration.get('type'),  # 'charge' or 'credit'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def invoice_download(request, invoice_id):
    """
    Download invoice as PDF.
    """
    invoice = get_object_or_404(Invoice, id=invoice_id)

    # Verify ownership
    if invoice.billing_cycle.subscription.user != request.user:
        return HttpResponseForbidden('You do not have access to this invoice.')

    # TODO: Implement PDF generation using reportlab or weasyprint
    # For now, return the invoice detail view
    return render(request, 'subscriptions/invoice_detail.html', {'invoice': invoice})


# ============================================================================
# Webhook Views
# ============================================================================

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import hmac
import hashlib


@csrf_exempt
@require_http_methods(["POST"])
def payment_webhook(request):
    """
    Webhook endpoint for payment provider callbacks.
    Handles payment success, failure, and other events.
    """
    try:
        # Verify webhook signature
        signature = request.META.get('HTTP_X_WEBHOOK_SIGNATURE', '')
        body = request.body

        # Verify signature (implementation depends on payment provider)
        # This is a placeholder - actual implementation varies
        expected_signature = hmac.new(
            settings.WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            return JsonResponse({'error': 'Invalid signature'}, status=403)

        # Parse webhook data
        data = json.loads(body)

        # Process webhook
        service = DunningService()
        service.handle_webhook(data)

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

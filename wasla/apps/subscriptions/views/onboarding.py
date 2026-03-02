"""
Onboarding views for the complete store setup flow.

Flow:
1. Plan Selection
2. Subdomain Selection
3. (PAID only) Payment Method Selection
4. (PAID only) Checkout & Payment
5. Success
"""

import logging
from django.conf import settings
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import HttpResponse

logger = logging.getLogger(__name__)
from apps.subscriptions.models import SubscriptionPlan
from apps.subscriptions.forms_onboarding import (
    PlanSelectForm,
    SubdomainSelectForm,
    PaymentMethodSelectForm,
    ManualPaymentUploadForm,
)
from apps.stores.models import Store
from apps.tenants.models import Tenant, StoreDomain
from apps.payments.models import ManualPayment


def _build_store_host(subdomain: str) -> str:
    base_domain = (getattr(settings, "WASSLA_BASE_DOMAIN", "w-sala.com") or "w-sala.com").strip().lower()
    return f"{subdomain}.{base_domain}"


def _build_dashboard_url(request, subdomain: str) -> str:
    scheme = "https" if request.is_secure() else "http"
    return f"{scheme}://{_build_store_host(subdomain)}/dashboard/"


def _get_onboarding_store(request, subdomain: str | None) -> Store | None:
    store_id = request.session.get("onboarding_store_id")
    if store_id:
        store = Store.objects.filter(id=store_id, owner=request.user).first()
        if store:
            return store
    if subdomain:
        return Store.objects.filter(subdomain=subdomain, owner=request.user).order_by("-created_at").first()
    return None


def _create_onboarding_store(request, plan: SubscriptionPlan, subdomain: str, *, status: str) -> Store:
    with transaction.atomic():
        tenant = Tenant.objects.create(
            name=f"{request.user.get_full_name() or request.user.username}'s Store",
            slug=subdomain,
            subdomain=subdomain,
            is_active=True,
            is_published=plan.is_free,
        )

        store = Store.objects.create(
            owner=request.user,
            tenant=tenant,
            name=f"{request.user.get_full_name() or request.user.username}'s Store",
            slug=subdomain,
            subdomain=subdomain,
            plan=plan,
            payment_method=None,
            status=status,
        )

        StoreDomain.objects.get_or_create(
            domain=_build_store_host(subdomain),
            defaults={
                "tenant": tenant,
                "store": store,
                "status": StoreDomain.STATUS_ACTIVE if plan.is_free else StoreDomain.STATUS_PENDING_VERIFICATION,
                "is_primary": True,
            },
        )
        return store


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_plan_select(request):
    """Step 1: User selects a subscription plan."""
    
    if request.method == "POST":
        form = PlanSelectForm(request.POST)
        if form.is_valid():
            plan_id = form.cleaned_data['plan_id'].id
            request.session['onboarding_plan_id'] = plan_id
            return redirect('subscriptions_web:onboarding_subdomain')
    else:
        form = PlanSelectForm()
    
    return render(request, 'subscriptions/onboarding/plan_select.html', {
        'form': form,
        'page_title': 'Choose Your Plan',
    })


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_subdomain_select(request):
    """Step 2: User selects a subdomain for their store."""
    
    # Verify plan was selected
    plan_id = request.session.get('onboarding_plan_id')
    if not plan_id:
        messages.warning(request, "Please select a plan first.")
        return redirect('subscriptions_web:onboarding_plan')
    
    try:
        plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
    except SubscriptionPlan.DoesNotExist:
        messages.error(request, "Selected plan is no longer available.")
        return redirect('subscriptions_web:onboarding_plan')
    
    if request.method == "POST":
        form = SubdomainSelectForm(request.POST)
        if form.is_valid():
            subdomain = form.cleaned_data['subdomain']
            request.session['onboarding_subdomain'] = subdomain
            
            # If FREE plan, skip payment and activate directly
            if plan.is_free:
                store = _create_onboarding_store(
                    request,
                    plan,
                    subdomain,
                    status=Store.STATUS_ACTIVE,
                )
                from apps.storefront.services import publish_default_storefront
                publish_default_storefront(store)
                messages.success(request, f"Welcome {request.user.first_name}! Your store is ready!")
                request.session.pop('onboarding_plan_id', None)
                request.session.pop('onboarding_subdomain', None)
                request.session.pop('onboarding_payment_method', None)
                request.session.pop('onboarding_store_id', None)
                return redirect(_build_dashboard_url(request, subdomain))
            
            # If PAID plan, go to payment method selection
            store = _get_onboarding_store(request, subdomain)
            if not store:
                store = _create_onboarding_store(
                    request,
                    plan,
                    subdomain,
                    status=Store.STATUS_PENDING_PAYMENT,
                )
            request.session['onboarding_store_id'] = store.id
            return redirect('subscriptions_web:onboarding_payment_method')
    else:
        form = SubdomainSelectForm()
    
    return render(request, 'subscriptions/onboarding/subdomain_select.html', {
        'form': form,
        'plan': plan,
        'page_title': 'Choose Your Store Subdomain',
    })


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_payment_method(request):
    """Step 3 (PAID only): User selects payment method."""
    
    plan_id = request.session.get('onboarding_plan_id')
    subdomain = request.session.get('onboarding_subdomain')
    
    if not plan_id or not subdomain:
        return redirect('subscriptions_web:onboarding_plan')
    
    try:
        plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
    except SubscriptionPlan.DoesNotExist:
        return redirect('subscriptions_web:onboarding_plan')
    
    # FREE plans should not reach here
    if plan.is_free:
        return redirect('subscriptions_web:onboarding_checkout')
    
    if request.method == "POST":
        form = PaymentMethodSelectForm(request.POST)
        if form.is_valid():
            payment_method = form.cleaned_data['payment_method']
            request.session['onboarding_payment_method'] = payment_method
            return redirect('subscriptions_web:onboarding_checkout')
    else:
        form = PaymentMethodSelectForm()
    
    return render(request, 'subscriptions/onboarding/payment_method_select.html', {
        'form': form,
        'plan': plan,
        'subdomain': subdomain,
        'page_title': 'Choose Payment Method',
    })


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_checkout(request):
    """
    Step 4: Checkout & Payment Execution
    
    For FREE plans: Creates store, activates, publishes, redirects to dashboard
    For PAID plans: Creates store as PENDING_PAYMENT, initiates payment
    """
    
    plan_id = request.session.get('onboarding_plan_id')
    subdomain = request.session.get('onboarding_subdomain')
    payment_method = request.session.get('onboarding_payment_method')
    
    if not plan_id or not subdomain:
        return redirect('subscriptions_web:onboarding_plan')
    
    try:
        plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
    except SubscriptionPlan.DoesNotExist:
        return redirect('subscriptions_web:onboarding_plan')
    
    if request.method == "POST":
        return _execute_onboarding_checkout(request, plan, subdomain, payment_method)
    
    # GET request - show confirmation page
    return render(request, 'subscriptions/onboarding/checkout.html', {
        'plan': plan,
        'subdomain': subdomain,
        'payment_method': payment_method if not plan.is_free else None,
        'is_free': plan.is_free,
        'page_title': 'Complete Your Order',
    })


def _execute_onboarding_checkout(request, plan, subdomain, payment_method):
    """
    Execute the onboarding checkout:
    - Create Tenant and Store
    - Handle FREE vs PAID flow
    """
    
    try:
        store = _get_onboarding_store(request, subdomain)
        if not store:
            store = _create_onboarding_store(
                request,
                plan,
                subdomain,
                status=Store.STATUS_PENDING_PAYMENT,
            )
            request.session['onboarding_store_id'] = store.id

        # Handle PAID plan: Create payment attempt
        if not payment_method:
            raise ValidationError("Payment method required for paid plans")

        store.payment_method = payment_method
        store.save(update_fields=["payment_method"])

        # Initiate payment based on provider
        if payment_method == 'stripe':
            return _initiate_stripe_payment(request, store, plan)
        elif payment_method == 'tap':
            return _initiate_tap_payment(request, store, plan)
        elif payment_method == 'manual':
            return redirect('subscriptions_web:onboarding_manual_payment')
        else:
            raise ValidationError(f"Unknown payment method: {payment_method}")

    except Exception as e:
        messages.error(request, f"Error creating store: {str(e)}")
        return redirect('subscriptions_web:onboarding_plan')


def _initiate_stripe_payment(request, store, plan):
    """Initiate Stripe payment for PAID plan using PaymentOrchestrator."""
    from apps.payments.orchestrator import PaymentOrchestrator
    from apps.tenants.domain.tenant_context import TenantContext
    from apps.orders.models import Order
    from django.urls import reverse
    
    try:
        # Create a temporary payment order for the subscription
        order = Order.objects.create(
            store=store,
            customer_email=request.user.email,
            status='pending_payment',
            total_amount=plan.price,
            currency='SAR',
            notes=f"Store activation payment - {store.subdomain}",
            payment_method='stripe'
        )
        
        # Build return URL for payment completion
        return_url = request.build_absolute_uri(
            reverse('subscriptions_web:onboarding_payment_callback')
        )
        
        # Build tenant context
        tenant_ctx = TenantContext(
            tenant_id=store.tenant.id,
            store_id=store.id,
            currency='SAR'
        )
        
        # Initiate Stripe payment session
        result = PaymentOrchestrator.initiate_payment(
            order=order,
            provider_code='stripe',
            tenant_ctx=tenant_ctx,
            return_url=return_url
        )
        
        # Store payment provider reference in session for webhook matching
        request.session['payment_provider_reference'] = result.provider_reference
        request.session['payment_order_id'] = order.id
        request.session.modified = True
        
        # Redirect to Stripe checkout
        return redirect(result.redirect_url)
        
    except Exception as e:
        messages.error(request, f"Payment initiation failed: {str(e)}")
        logger.exception(f"Stripe payment initiation failed for store {store.id}", exc_info=e)
        return redirect('subscriptions_web:onboarding_payment_method')


def _initiate_tap_payment(request, store, plan):
    """Initiate Tap payment for PAID plan using PaymentOrchestrator."""
    from apps.payments.orchestrator import PaymentOrchestrator
    from apps.tenants.domain.tenant_context import TenantContext
    from apps.orders.models import Order
    from django.urls import reverse
    
    try:
        # Create a temporary payment order for the subscription
        order = Order.objects.create(
            store=store,
            customer_email=request.user.email,
            status='pending_payment',
            total_amount=plan.price,
            currency='SAR',
            notes=f"Store activation payment - {store.subdomain}",
            payment_method='tap'
        )
        
        # Build return URL for payment completion
        return_url = request.build_absolute_uri(
            reverse('subscriptions_web:onboarding_payment_callback')
        )
        
        # Build tenant context
        tenant_ctx = TenantContext(
            tenant_id=store.tenant.id,
            store_id=store.id,
            currency='SAR'
        )
        
        # Initiate Tap payment session
        result = PaymentOrchestrator.initiate_payment(
            order=order,
            provider_code='tap',
            tenant_ctx=tenant_ctx,
            return_url=return_url
        )
        
        # Store payment provider reference in session for webhook matching
        request.session['payment_provider_reference'] = result.provider_reference
        request.session['payment_order_id'] = order.id
        request.session.modified = True
        
        # Redirect to Tap hosted payment
        return redirect(result.redirect_url)
        
    except Exception as e:
        messages.error(request, f"Payment initiation failed: {str(e)}")
        logger.exception(f"Tap payment initiation failed for store {store.id}", exc_info=e)
        return redirect('subscriptions_web:onboarding_payment_method')


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_manual_payment(request):
    """Handle manual payment submission for PAID plans."""
    
    plan_id = request.session.get('onboarding_plan_id')
    subdomain = request.session.get('onboarding_subdomain')
    
    if not plan_id or not subdomain:
        return redirect('subscriptions_web:onboarding_plan')
    
    # Get the store created in checkout (should exist as pending payment)
    store = _get_onboarding_store(request, subdomain)
    if store and store.status != Store.STATUS_PENDING_PAYMENT:
        store = None
    
    if not store:
        messages.error(request, "Store not found. Please start onboarding again.")
        return redirect('subscriptions_web:onboarding_plan')
    
    plan = store.plan
    if plan.is_free:
        return redirect('subscriptions_web:onboarding_success')
    
    if request.method == "POST":
        form = ManualPaymentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Create ManualPayment record
            manual_payment = ManualPayment.objects.create(
                store=store,
                plan=plan,
                amount=plan.price,
                currency='SAR',
                reference=form.cleaned_data['reference'],
                receipt_file=form.cleaned_data.get('receipt_file'),
                notes_user=form.cleaned_data['notes'],
                status=ManualPayment.STATUS_PENDING,
            )
            
            messages.success(
                request,
                "Payment proof submitted! Our team will review it within 24 hours."
            )
            request.session.pop('onboarding_plan_id', None)
            request.session.pop('onboarding_subdomain', None)
            request.session.pop('onboarding_payment_method', None)
            return redirect('subscriptions_web:onboarding_success')
    else:
        form = ManualPaymentUploadForm()
    
    return render(request, 'subscriptions/onboarding/manual_payment.html', {
        'form': form,
        'store': store,
        'plan': plan,
        'subdomain': subdomain,
        'page_title': 'Submit Manual Payment',
        'bank_details': {
            'account_name': 'Wasla Commerce',
            'account_number': 'SA0000000000000000000000',  # Placeholder
            'iban': 'SA00 XXXX XXXX XXXX XXXX XXXX',
            'bank_name': 'Arab National Bank',
        }
    })


@login_required
def onboarding_success(request):
    """Success page after onboarding completion."""
    
    # Get user's most recent store
    store = Store.objects.filter(owner=request.user).order_by('-created_at').first()
    
    return render(request, 'subscriptions/onboarding/success.html', {
        'store': store,
        'page_title': 'Onboarding Complete',
    })

@login_required
def onboarding_payment_callback(request):
    """
    Callback from Stripe/Tap after payment.
    
    The webhook handler will activate the store when payment confirmed.
    This view just displays status to user.
    """
    from apps.orders.models import Order
    
    order_id = request.session.get('payment_order_id')
    
    if not order_id:
        messages.info(request, "Payment processing. Please wait for confirmation.")
        return redirect('subscriptions_web:onboarding_success')
    
    try:
        order = Order.objects.get(id=order_id)
        store = order.store
        
        # Check if store already activated (webhook processed)
        if store.status == Store.STATUS_ACTIVE:
            messages.success(request, "Store activated! Redirecting...")
            return redirect('subscriptions_web:onboarding_success')
        
        # Still pending - webhook might still be processing
        if store.status == Store.STATUS_PENDING_PAYMENT:
            messages.info(request, "Payment received. Activating your store...")
            return render(request, 'subscriptions/onboarding/payment_processing.html', {
                'store': store,
                'page_title': 'Processing Payment',
            })
        
        messages.success(request, "Setup complete!")
        return redirect('subscriptions_web:onboarding_success')
        
    except Order.DoesNotExist:
        messages.error(request, "Payment not found")
        return redirect('subscriptions_web:onboarding_plan')

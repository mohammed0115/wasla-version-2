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
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)
from apps.subscriptions.models import SubscriptionPlan
from apps.subscriptions.forms_onboarding import (
    PlanSelectForm,
    SubdomainSelectForm,
    PaymentMethodSelectForm,
    ManualPaymentUploadForm,
)
from apps.stores.models import Store
from apps.tenants.models import Tenant
from apps.subscriptions.services.onboarding_utils import (
    build_store_dashboard_url,
    build_store_host,
    ensure_store_domain_mapping,
    enqueue_store_welcome_email,
    get_base_domain,
)
from apps.tenants.services.domain_resolution import normalize_subdomain_label, validate_subdomain


def _resolve_store_plan(plan: SubscriptionPlan):
    from apps.stores.models import Plan as StorePlan

    if isinstance(plan, StorePlan):
        return plan
    if hasattr(plan, "name"):
        return StorePlan.objects.filter(name=plan.name).first()
    return None


def _plan_price(plan: object):
    if hasattr(plan, "price") and getattr(plan, "price") is not None:
        return getattr(plan, "price")
    if hasattr(plan, "price_monthly") and getattr(plan, "price_monthly") is not None:
        return getattr(plan, "price_monthly")
    return 0


def _plan_is_free(plan: object) -> bool:
    if getattr(plan, "is_free", False):
        return True
    return _plan_price(plan) == 0


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
    is_valid, error_msg = validate_subdomain(subdomain)
    if not is_valid:
        raise ValidationError(error_msg)

    normalized_subdomain = normalize_subdomain_label(subdomain)
    if not normalized_subdomain:
        raise ValidationError("Use only letters, numbers, hyphen")

    store_plan = _resolve_store_plan(plan)

    with transaction.atomic():
        tenant = Tenant.objects.create(
            name=f"{request.user.get_full_name() or request.user.username}'s Store",
            slug=normalized_subdomain,
            subdomain=normalized_subdomain,
            is_active=True,
            is_published=_plan_is_free(plan),
        )

        store = Store.objects.create(
            owner=request.user,
            tenant=tenant,
            name=f"{request.user.get_full_name() or request.user.username}'s Store",
            slug=normalized_subdomain,
            subdomain=normalized_subdomain,
            plan=store_plan,
            status=status,
        )

        ensure_store_domain_mapping(store)
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
        'base_domain': get_base_domain(),
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
            if _plan_is_free(plan):
                store = _create_onboarding_store(
                    request,
                    plan,
                    subdomain,
                    status=Store.STATUS_ACTIVE,
                )
                from apps.storefront.services import publish_default_storefront
                try:
                    publish_default_storefront(store)
                except Exception as exc:
                    logger.warning("Default storefront publish skipped for store %s", store.id, exc_info=exc)
                enqueue_store_welcome_email(store=store, to_email=request.user.email)
                messages.success(request, f"Welcome {request.user.first_name}! Your store is ready!")
                request.session.pop('onboarding_plan_id', None)
                request.session.pop('onboarding_subdomain', None)
                request.session.pop('onboarding_payment_method', None)
                request.session.pop('onboarding_store_id', None)
                return redirect(build_store_dashboard_url(store.subdomain))
            
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
        'base_domain': get_base_domain(),
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
    if _plan_is_free(plan):
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
        'plan_price': _plan_price(plan),
        'subdomain': subdomain,
        'page_title': 'Choose Payment Method',
        'base_domain': get_base_domain(),
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
        'payment_method': payment_method if not _plan_is_free(plan) else None,
        'is_free': _plan_is_free(plan),
        'plan_price': _plan_price(plan),
        'page_title': 'Complete Your Order',
        'base_domain': get_base_domain(),
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
            total_amount=_plan_price(plan),
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
            total_amount=_plan_price(plan),
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
    if plan_id:
        plan = SubscriptionPlan.objects.filter(id=plan_id).first() or plan
    if _plan_is_free(plan):
        return redirect('subscriptions_web:onboarding_success')
    
    if request.method == "POST":
        form = ManualPaymentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            from apps.payments.models import ManualPayment

            # Create ManualPayment record
            manual_payment = ManualPayment.objects.create(
                store=store,
                plan=plan,
                amount=_plan_price(plan),
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
        'plan_price': _plan_price(plan),
        'subdomain': subdomain,
        'page_title': 'Submit Manual Payment',
        'base_domain': get_base_domain(),
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
    store_id = request.session.get("onboarding_store_id")
    store = None
    if store_id:
        store = Store.objects.filter(id=store_id, owner=request.user).first()
    if not store:
        store = Store.objects.filter(owner=request.user).order_by('-created_at').first()

    base_domain = get_base_domain()
    store_host = build_store_host(store.subdomain) if store else ""
    store_dashboard_url = build_store_dashboard_url(store.subdomain) if store else ""
    store_front_url = f"https://{store_host}" if store_host else ""
    
    return render(request, 'subscriptions/onboarding/success.html', {
        'store': store,
        'page_title': 'Onboarding Complete',
        'base_domain': base_domain,
        'store_host': store_host,
        'store_dashboard_url': store_dashboard_url,
        'store_front_url': store_front_url,
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
            ensure_store_domain_mapping(store)
            return redirect(build_store_dashboard_url(store.subdomain))
        
        # Still pending - webhook might still be processing
        if store.status == Store.STATUS_PENDING_PAYMENT:
            messages.info(request, "Payment received. Activating your store...")
            return render(request, 'subscriptions/onboarding/payment_processing.html', {
                'store': store,
                'page_title': 'Processing Payment',
                'base_domain': get_base_domain(),
            })
        
        messages.success(request, "Setup complete!")
        return redirect('subscriptions_web:onboarding_success')
        
    except Order.DoesNotExist:
        messages.error(request, "Payment not found")
        return redirect('subscriptions_web:onboarding_plan')


@login_required
def onboarding_dashboard_redirect(request, store_id: int):
    store = Store.objects.filter(id=store_id, owner=request.user).first()
    if not store:
        messages.error(request, "Store not found.")
        return redirect('subscriptions_web:onboarding_plan')

    ensure_store_domain_mapping(store)
    return redirect(build_store_dashboard_url(store.subdomain))


@login_required
def go_to_dashboard(request):
    store = Store.objects.filter(owner=request.user).order_by("-created_at").first()
    if not store:
        try:
            from apps.tenants.models import TenantMembership, StoreProfile

            membership = (
                TenantMembership.objects.select_related("tenant")
                .filter(user=request.user, is_active=True, tenant__is_active=True)
                .order_by("-tenant_id")
                .first()
            )
            if membership:
                store = Store.objects.filter(tenant=membership.tenant).order_by("-created_at").first()
            if not store:
                profile = (
                    StoreProfile.objects.select_related("tenant")
                    .filter(owner=request.user, tenant__is_active=True)
                    .order_by("-tenant_id")
                    .first()
                )
                if profile:
                    store = Store.objects.filter(tenant=profile.tenant).order_by("-created_at").first()
        except Exception:
            store = None

    if not store:
        messages.error(request, "Store not found. Please start onboarding again.")
        return redirect('subscriptions_web:onboarding_plan')

    ensure_store_domain_mapping(store)
    return redirect(build_store_dashboard_url(store.subdomain))

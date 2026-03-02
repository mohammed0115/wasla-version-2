from __future__ import annotations

from datetime import timedelta
from functools import wraps

from django.contrib.auth.decorators import login_required

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from apps.tenants.domain.errors import StoreAccessDeniedError, StoreInactiveError
from apps.tenants.models import StoreProfile, Tenant, TenantMembership
from apps.subscriptions.models import StoreSubscription
from apps.subscriptions.models import PaymentTransaction
from apps.subscriptions.services.subscription_service import SubscriptionService
from apps.tenants.services.provisioning import merchant_has_active_store


def resolve_tenant_for_request(request: HttpRequest) -> Tenant | None:
    tenant = getattr(request, "tenant", None)
    if isinstance(tenant, Tenant):
        return tenant

    store_id = request.session.get("store_id")
    try:
        store_id = int(store_id) if store_id is not None else None
    except (TypeError, ValueError):
        store_id = None

    if store_id:
        tenant = Tenant.objects.filter(id=store_id, is_active=True).first()
        if tenant:
            request.tenant = tenant
            return tenant

    membership = (
        TenantMembership.objects.select_related("tenant")
        .filter(
            user=request.user,
            role=TenantMembership.ROLE_OWNER,
            is_active=True,
            tenant__is_active=True,
        )
        .order_by("tenant_id")
        .first()
    )
    if membership:
        request.session["store_id"] = membership.tenant_id
        request.tenant = membership.tenant
        return membership.tenant

    profile = (
        StoreProfile.objects.select_related("tenant")
        .filter(owner=request.user, tenant__is_active=True)
        .order_by("tenant_id")
        .first()
    )
    if profile:
        request.session["store_id"] = profile.tenant_id
        request.tenant = profile.tenant
        return profile.tenant

    return None


def tenant_access_required(view_func):
    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        tenant = resolve_tenant_for_request(request)
        if not tenant:
            return redirect("tenants:dashboard_setup_store")

        try:
            EnsureTenantOwnershipPolicy.ensure_can_access(user=request.user, tenant=tenant)
        except (StoreAccessDeniedError, StoreInactiveError) as exc:
            return render(
                request,
                "dashboard/access_denied.html",
                {"message": str(exc)},
                status=403,
            )

        request.session["store_id"] = tenant.id
        request.tenant = tenant
        return view_func(request, *args, **kwargs)

    return _wrapped


def _latest_subscription(tenant_id: int) -> StoreSubscription | None:
    return (
        StoreSubscription.objects.filter(store_id=tenant_id)
        .select_related("plan")
        .order_by("-created_at", "-end_date")
        .first()
    )


def _is_subscription_entitled(subscription: StoreSubscription | None) -> bool:
    return SubscriptionService.is_subscription_entitled(subscription)


def _has_submitted_payment(tenant_id: int) -> bool:
    return PaymentTransaction.objects.filter(tenant_id=tenant_id).exclude(
        status__in=[
            PaymentTransaction.STATUS_FAILED,
            PaymentTransaction.STATUS_CANCELLED,
        ]
    ).exists()


def _billing_redirect_for_tenant(tenant_id: int):
    if _has_submitted_payment(tenant_id):
        return redirect("tenants:billing_pending_activation")
    return redirect("tenants:billing_payment_required")


def merchant_dashboard_required(view_func):
    """Require tenant ownership + active subscription + published store."""

    @login_required
    def _wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        tenant = resolve_tenant_for_request(request)
        if not tenant:
            return redirect("tenants:dashboard_setup_store")

        try:
            EnsureTenantOwnershipPolicy.ensure_can_access(user=request.user, tenant=tenant)
        except (StoreAccessDeniedError, StoreInactiveError) as exc:
            return render(
                request,
                "dashboard/access_denied.html",
                {"message": str(exc)},
                status=403,
            )

        request.session["store_id"] = tenant.id
        request.tenant = tenant

        if not merchant_has_active_store(request.user):
            return _billing_redirect_for_tenant(tenant.id)

        subscription = _latest_subscription(tenant.id)
        if subscription is None:
            return _billing_redirect_for_tenant(tenant.id)
        if not _is_subscription_entitled(subscription):
            return _billing_redirect_for_tenant(tenant.id)
        if not getattr(tenant, "is_published", False):
            return redirect("tenants:billing_pending_activation")

        return view_func(request, *args, **kwargs)

    return _wrapped


def merchant_subscription_required(view_func):
    """Require tenant ownership + active subscription (no publish requirement)."""

    @login_required
    def _wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        tenant = resolve_tenant_for_request(request)
        if not tenant:
            return redirect("tenants:dashboard_setup_store")

        try:
            EnsureTenantOwnershipPolicy.ensure_can_access(user=request.user, tenant=tenant)
        except (StoreAccessDeniedError, StoreInactiveError) as exc:
            return render(
                request,
                "dashboard/access_denied.html",
                {"message": str(exc)},
                status=403,
            )

        request.session["store_id"] = tenant.id
        request.tenant = tenant

        if not merchant_has_active_store(request.user):
            return _billing_redirect_for_tenant(tenant.id)

        subscription = _latest_subscription(tenant.id)
        if subscription is None:
            return _billing_redirect_for_tenant(tenant.id)
        if not _is_subscription_entitled(subscription):
            return _billing_redirect_for_tenant(tenant.id)

        return view_func(request, *args, **kwargs)

    return _wrapped

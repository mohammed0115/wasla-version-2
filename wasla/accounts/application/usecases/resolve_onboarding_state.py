from __future__ import annotations

from django.conf import settings
from django.db.models import Case, IntegerField, Value, When
from django.shortcuts import resolve_url
from django.urls import reverse

from subscriptions.services.subscription_service import SubscriptionService
from tenants.application.use_cases.store_setup_wizard import StoreSetupWizardUseCase
from tenants.models import StoreProfile, Tenant, TenantMembership


def _resolve_tenant_for_user(request) -> Tenant | None:
    tenant = getattr(request, "tenant", None)
    if isinstance(tenant, Tenant) and tenant.is_active:
        return tenant

    raw_store_id = request.session.get("store_id") if hasattr(request, "session") else None
    try:
        store_id = int(raw_store_id) if raw_store_id is not None else None
    except (TypeError, ValueError):
        store_id = None

    if store_id:
        by_session = Tenant.objects.filter(id=store_id, is_active=True).first()
        if by_session:
            request.tenant = by_session
            return by_session

    memberships = (
        TenantMembership.objects.select_related("tenant")
        .filter(user=request.user, is_active=True, tenant__is_active=True)
        .annotate(
            owner_rank=Case(
                When(role=TenantMembership.ROLE_OWNER, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("owner_rank", "tenant_id")
    )
    membership = memberships.first()
    if membership:
        if hasattr(request, "session"):
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
        if hasattr(request, "session"):
            request.session["store_id"] = profile.tenant_id
        request.tenant = profile.tenant
        return profile.tenant

    return None


def resolve_onboarding_state(request) -> str:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return str(resolve_url(settings.LOGIN_URL))

    profile = getattr(user, "profile", None)
    if not profile or not bool(getattr(profile, "persona_completed", False)):
        return reverse("accounts:persona_welcome")

    tenant = _resolve_tenant_for_user(request)
    if tenant is None:
        return reverse("tenants:store_create")

    active_subscription = SubscriptionService.get_active_subscription(tenant.id)
    if active_subscription is None:
        return reverse("accounts:persona_plans")

    store_profile = StoreProfile.objects.filter(tenant=tenant).order_by("id").first()
    if not store_profile:
        return reverse("tenants:dashboard_setup_store")

    state = StoreSetupWizardUseCase.get_state(profile=store_profile)
    if not store_profile.is_setup_complete:
        if state.current_step <= StoreSetupWizardUseCase.STEP_STORE_INFO:
            return reverse("tenants:dashboard_setup_store")
        if state.current_step == StoreSetupWizardUseCase.STEP_PAYMENT:
            return reverse("tenants:dashboard_setup_payment")
        if state.current_step == StoreSetupWizardUseCase.STEP_SHIPPING:
            return reverse("tenants:dashboard_setup_shipping")
        if state.current_step == StoreSetupWizardUseCase.STEP_FIRST_PRODUCT:
            return reverse("tenants:dashboard_setup_activate")

    return "/dashboard/"

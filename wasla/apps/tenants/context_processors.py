from __future__ import annotations

from apps.subscriptions.models import StoreSubscription
from apps.tenants.models import StoreProfile, Tenant, TenantMembership


def merchant_status_context(request):
    """Inject current plan/subscription/store status for merchant dashboard UI."""
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {}

    tenant = getattr(request, "tenant", None)
    if not isinstance(tenant, Tenant):
        membership = (
            TenantMembership.objects.select_related("tenant")
            .filter(user=user, is_active=True, tenant__is_active=True)
            .order_by("tenant_id")
            .first()
        )
        if membership:
            tenant = membership.tenant
        else:
            profile = (
                StoreProfile.objects.select_related("tenant")
                .filter(owner=user, tenant__is_active=True)
                .order_by("tenant_id")
                .first()
            )
            if profile:
                tenant = profile.tenant

    if not isinstance(tenant, Tenant):
        return {}

    subscription = (
        StoreSubscription.objects.filter(store_id=tenant.id)
        .select_related("plan")
        .order_by("-created_at", "-end_date")
        .first()
    )

    return {
        "merchant_tenant": tenant,
        "merchant_subscription": subscription,
        "merchant_plan": subscription.plan if subscription else None,
    }

from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.catalog.models import Product
from apps.tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from apps.tenants.domain.errors import StoreAccessDeniedError, StoreInactiveError
from apps.tenants.domain.visibility import StorefrontState, get_storefront_state
from apps.tenants.models import Tenant


def _get_tenant_from_request(request: HttpRequest) -> Tenant:
    tenant = getattr(request, "tenant", None)
    if not isinstance(tenant, Tenant):
        raise Http404("Store not found.")
    return tenant


@require_GET
def storefront_home(request: HttpRequest) -> HttpResponse:
    tenant = _get_tenant_from_request(request)

    state = get_storefront_state(
        tenant_is_active=tenant.is_active,
        is_published=tenant.is_published,
        activated_at=tenant.activated_at,
        deactivated_at=tenant.deactivated_at,
    )

    preview = False
    if state != StorefrontState.LIVE and getattr(request.user, "is_authenticated", False):
        try:
            EnsureTenantOwnershipPolicy.ensure_can_access(user=request.user, tenant=tenant)
        except (StoreAccessDeniedError, StoreInactiveError):
            preview = False
        else:
            preview = True
            state = StorefrontState.LIVE

    if state == StorefrontState.MAINTENANCE:
        return render(request, "storefront/maintenance.html", {"tenant": tenant})
    if state == StorefrontState.COMING_SOON:
        return render(request, "storefront/coming_soon.html", {"tenant": tenant})

    products = (
        Product.objects.filter(store_id=tenant.id, is_active=True)
        .order_by("-id")
        .only("id", "name", "price", "image", "sku")[:24]
    )
    return render(
        request,
        "storefront/home.html",
        {"tenant": tenant, "products": products, "preview": preview},
    )


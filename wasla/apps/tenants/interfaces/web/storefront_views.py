from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.catalog.models import Product
from apps.subscriptions.models import StoreSubscription
from apps.subscriptions.services.subscription_service import SubscriptionService
from core.infrastructure.store_cache import StoreCacheService
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

    category_id = (request.GET.get("category") or "").strip()
    query = (request.GET.get("q") or "").strip()

    def _load_products():
        queryset = Product.objects.filter(store_id=tenant.id, is_active=True)
        if category_id:
            queryset = queryset.filter(categories__id=category_id)
        if query:
            queryset = queryset.filter(name__icontains=query)
        return list(queryset.order_by("-id").only("id", "name", "price", "image", "sku")[:24])

    def _load_store_config():
        active_subscription = SubscriptionService.get_active_subscription(tenant.id)
        plan = getattr(active_subscription, "plan", None)
        return {
            "theme": {
                "primary_color": getattr(tenant, "primary_color", "") or "",
                "secondary_color": getattr(tenant, "secondary_color", "") or "",
            },
            "plan": {
                "id": getattr(plan, "id", None),
                "name": getattr(plan, "name", "") if plan else "",
                "max_products": getattr(plan, "max_products", None) if plan else None,
            },
            "domain": {
                "domain": getattr(tenant, "domain", "") or "",
                "subdomain": getattr(tenant, "subdomain", "") or "",
            },
        }

    products, _ = StoreCacheService.get_or_set(
        store_id=tenant.id,
        namespace="storefront_products",
        key_parts=["home", getattr(request, "LANGUAGE_CODE", "ar"), f"c:{category_id or 'all'}", f"q:{query or 'all'}"],
        producer=_load_products,
        timeout=180,
    )
    store_config, _ = StoreCacheService.get_or_set(
        store_id=tenant.id,
        namespace="store_config",
        key_parts=["theme", "domain"],
        producer=_load_store_config,
        timeout=300,
    )
    return render(
        request,
        "storefront/home.html",
        {
            "tenant": tenant,
            "products": products,
            "preview": preview,
            "store_config": store_config,
        },
    )


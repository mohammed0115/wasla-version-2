from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import FieldDoesNotExist

from apps.tenants.domain.policies import normalize_domain
from apps.tenants.models import StoreDomain, Tenant
from apps.stores.models import Store


def _cache_key(host: str) -> str:
    return f"tenant_by_host:{host}"


def _store_cache_key(slug: str) -> str:
    return f"store_by_slug:{slug}"


def resolve_tenant_by_host(host: str) -> Tenant | None:
    normalized = normalize_domain(host)
    if not normalized:
        return None

    cache_timeout = int(getattr(settings, "CUSTOM_DOMAIN_CACHE_SECONDS", 300) or 300)
    cached = cache.get(_cache_key(normalized))
    if cached is not None:
        if cached == 0:
            return None
        return Tenant.objects.filter(id=cached, is_active=True).first()

    tenant = _resolve_uncached(normalized)
    cache.set(_cache_key(normalized), tenant.id if tenant else 0, cache_timeout)
    return tenant


def invalidate_domain_cache(host: str) -> None:
    normalized = normalize_domain(host)
    if not normalized:
        return
    cache.delete(_cache_key(normalized))


def resolve_store_by_slug(slug: str) -> "Store | None":
    """Resolve a store by its slug with caching."""
    normalized = (slug or "").strip().lower()
    if not normalized:
        return None

    cache_timeout = int(
        getattr(settings, "STORE_SLUG_CACHE_SECONDS", getattr(settings, "CACHE_TTL_DEFAULT", 300) or 300)
    )
    cached = cache.get(_store_cache_key(normalized))
    if cached is not None:
        if cached == 0:
            return None
        return Store.objects.select_related("tenant").filter(id=cached).first()

    store = _resolve_store_by_slug_uncached(normalized)
    cache.set(_store_cache_key(normalized), store.id if store else 0, cache_timeout)
    return store


def invalidate_store_slug_cache(slug: str) -> None:
    normalized = (slug or "").strip().lower()
    if not normalized:
        return
    cache.delete(_store_cache_key(normalized))


def _resolve_store_by_slug_uncached(slug: str) -> "Store | None":
    if not slug:
        return None

    try:
        store_qs = Store.objects.select_related("tenant").filter(slug=slug)
        try:
            Store._meta.get_field("is_active")
            store_qs = store_qs.filter(is_active=True)
        except FieldDoesNotExist:
            try:
                Store._meta.get_field("status")
                store_qs = store_qs.filter(status=Store.STATUS_ACTIVE)
            except Exception:
                pass

        store = store_qs.first()
        return store
    except Exception:
        return None


def _resolve_uncached(host: str) -> Tenant | None:
    # Use defensive getattr for backward compatibility with older migrations
    status_active = getattr(StoreDomain, "STATUS_ACTIVE", "active")
    status_degraded = getattr(StoreDomain, "STATUS_DEGRADED", "degraded")
    
    domain_match = (
        StoreDomain.objects.select_related("tenant")
        .filter(
            domain=host,
            status__in=(status_active, status_degraded),
            tenant__is_active=True,
        )
        .first()
    )
    if domain_match:
        return domain_match.tenant

    legacy_tenant = Tenant.objects.filter(domain=host, is_active=True).first()
    if legacy_tenant:
        return legacy_tenant

    base_domain = normalize_domain(getattr(settings, "WASSLA_BASE_DOMAIN", ""))
    if base_domain and host.endswith(f".{base_domain}"):
        sub = host[: -(len(base_domain) + 1)]
        sub = sub.split(".")[0] if sub else ""
        if sub:
            tenant = Tenant.objects.filter(slug=sub, is_active=True).first()
            if tenant:
                return tenant
            tenant = Tenant.objects.filter(subdomain=sub, is_active=True).first()
            if tenant:
                return tenant
    return None

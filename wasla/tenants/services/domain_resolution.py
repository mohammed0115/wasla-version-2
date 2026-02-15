from __future__ import annotations

from django.conf import settings
from django.core.cache import cache

from tenants.domain.policies import normalize_domain
from tenants.models import StoreDomain, Tenant


def _cache_key(host: str) -> str:
    return f"tenant_by_host:{host}"


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


def _resolve_uncached(host: str) -> Tenant | None:
    domain_match = (
        StoreDomain.objects.select_related("tenant")
        .filter(
            domain=host,
            status__in=(StoreDomain.STATUS_ACTIVE, StoreDomain.STATUS_SSL_ACTIVE),
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

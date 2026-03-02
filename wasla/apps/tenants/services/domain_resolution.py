from __future__ import annotations

import ipaddress
import re

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


def _store_subdomain_cache_key(subdomain: str) -> str:
    return f"store_by_subdomain:{subdomain}"


def _store_host_cache_key(host: str) -> str:
    return f"store_by_host:{host}"


_SUBDOMAIN_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalize_host(raw_host: str) -> str:
    raw = (raw_host or "").strip().lower()
    if not raw:
        return ""

    if raw.startswith("["):
        end = raw.find("]")
        if end != -1:
            raw = raw[1:end]
        else:
            raw = raw.lstrip("[")
    else:
        raw = raw.split(":", 1)[0]

    raw = normalize_domain(raw)
    if not raw:
        return ""
    try:
        ipaddress.ip_address(raw)
        return ""
    except ValueError:
        return raw


def normalize_subdomain_label(raw: str) -> str:
    value = (raw or "").strip().lower()
    if not value:
        return ""
    label = value.split(".", 1)[0]
    cleaned = re.sub(r"[^a-z0-9-]", "", label)
    cleaned = cleaned.strip("-")
    if len(cleaned) > 63:
        cleaned = cleaned[:63]
    return cleaned


def validate_subdomain(raw: str) -> tuple[bool, str]:
    """Validate user-provided subdomain input for onboarding UI."""
    value = (raw or "").strip().lower()
    if not value:
        return False, "Subdomain is required."
    if "@" in value or "." in value:
        return False, "Use only letters, numbers, hyphen"
    normalized = normalize_subdomain_label(value)
    if not normalized or not _SUBDOMAIN_SLUG_RE.match(normalized):
        return False, "Use only letters, numbers, hyphen"
    if Store.objects.filter(subdomain=normalized).exists():
        return False, "This subdomain is already taken."
    if Store.objects.filter(slug=normalized).exists():
        return False, "This subdomain is already taken."
    if Tenant.objects.filter(slug=normalized).exists():
        return False, "This subdomain is already taken."
    return True, ""


def resolve_platform_store() -> "Store | None":
    store_qs = Store.objects.select_related("tenant").filter(is_platform_default=True)
    try:
        Store._meta.get_field("is_active")
        store_qs = store_qs.filter(is_active=True)
    except FieldDoesNotExist:
        try:
            Store._meta.get_field("status")
            store_qs = store_qs.filter(status=Store.STATUS_ACTIVE)
        except Exception:
            pass
    return store_qs.first()


def resolve_tenant_by_host(host: str) -> Tenant | None:
    normalized = normalize_host(host)
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
    normalized = normalize_host(host)
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


def resolve_store_by_subdomain(subdomain: str) -> "Store | None":
    """Resolve a store by its subdomain with caching."""
    normalized = normalize_subdomain_label(subdomain)
    if not normalized:
        return None

    cache_timeout = int(
        getattr(settings, "STORE_SLUG_CACHE_SECONDS", getattr(settings, "CACHE_TTL_DEFAULT", 300) or 300)
    )
    cached = cache.get(_store_subdomain_cache_key(normalized))
    if cached is not None:
        if cached == 0:
            return None
        return Store.objects.select_related("tenant").filter(id=cached).first()

    store = _resolve_store_by_subdomain_uncached(normalized)
    cache.set(_store_subdomain_cache_key(normalized), store.id if store else 0, cache_timeout)
    return store


def invalidate_store_slug_cache(slug: str) -> None:
    normalized = (slug or "").strip().lower()
    if not normalized:
        return
    cache.delete(_store_cache_key(normalized))


def invalidate_store_subdomain_cache(subdomain: str) -> None:
    normalized = normalize_subdomain_label(subdomain)
    if not normalized:
        return
    cache.delete(_store_subdomain_cache_key(normalized))


def invalidate_store_host_cache(host: str) -> None:
    normalized = normalize_host(host)
    if not normalized:
        return
    cache.delete(_store_host_cache_key(normalized))


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


def _resolve_store_by_subdomain_uncached(subdomain: str) -> "Store | None":
    if not subdomain:
        return None
    try:
        return Store.objects.select_related("tenant").filter(subdomain=subdomain).first()
    except Exception:
        return None


def resolve_store_by_host(host: str, *, allow_auto_create: bool = True) -> "Store | None":
    normalized_host = normalize_host(host)
    if not normalized_host:
        return None

    cache_timeout = int(getattr(settings, "CUSTOM_DOMAIN_CACHE_SECONDS", 300) or 300)
    cached = cache.get(_store_host_cache_key(normalized_host))
    if cached is not None:
        if cached == 0:
            return None
        return Store.objects.select_related("tenant").filter(id=cached).first()

    store = _resolve_store_by_host_uncached(normalized_host, allow_auto_create=allow_auto_create)
    cache.set(_store_host_cache_key(normalized_host), store.id if store else 0, cache_timeout)
    return store


def _resolve_store_by_host_uncached(host: str, *, allow_auto_create: bool) -> "Store | None":
    base_domain = normalize_domain(getattr(settings, "WASSLA_BASE_DOMAIN", ""))
    status_active = getattr(StoreDomain, "STATUS_ACTIVE", "active")
    status_degraded = getattr(StoreDomain, "STATUS_DEGRADED", "degraded")

    domain_qs = StoreDomain.objects.select_related("store", "tenant").filter(domain=host)
    if base_domain and not host.endswith(f".{base_domain}") and host not in {base_domain, f"www.{base_domain}"}:
        domain_qs = domain_qs.filter(status__in=(status_active, status_degraded))

    domain_match = domain_qs.first()
    if domain_match:
        store = domain_match.store
        if not store and domain_match.tenant_id:
            store = Store.objects.filter(tenant_id=domain_match.tenant_id).order_by("id").first()
            if store and allow_auto_create:
                StoreDomain.objects.filter(id=domain_match.id).update(store_id=store.id)
        if store:
            return store

    if base_domain and host.endswith(f".{base_domain}"):
        sub = host[: -(len(base_domain) + 1)]
        sub = sub.split(".", 1)[0] if sub else ""
        normalized_sub = normalize_subdomain_label(sub)
        if normalized_sub and _SUBDOMAIN_SLUG_RE.match(normalized_sub):
            store = resolve_store_by_subdomain(normalized_sub)
            if not store:
                store = resolve_store_by_slug(normalized_sub)
            if store and allow_auto_create:
                _ensure_store_domain_mapping(host=host, store=store)
            return store

    return None


def _ensure_store_domain_mapping(*, host: str, store: Store) -> StoreDomain | None:
    normalized_host = normalize_host(host)
    if not normalized_host:
        return None
    try:
        domain, created = StoreDomain.objects.get_or_create(
            domain=normalized_host,
            defaults={
                "tenant": store.tenant,
                "store": store,
                "status": getattr(StoreDomain, "STATUS_ACTIVE", "active"),
                "is_primary": True,
                "verification_token": StoreDomain.generate_verification_token(),
            },
        )
        if not created:
            updates = {}
            if domain.store_id is None:
                updates["store_id"] = store.id
            if domain.tenant_id is None and store.tenant_id:
                updates["tenant_id"] = store.tenant_id
            if not domain.verification_token:
                updates["verification_token"] = StoreDomain.generate_verification_token()
            if updates:
                StoreDomain.objects.filter(id=domain.id).update(**updates)
        return domain
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

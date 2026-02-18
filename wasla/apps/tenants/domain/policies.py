from __future__ import annotations

import re

from .errors import (
    CustomDomainInvalidError,
    CustomDomainNotAllowedError,
    CustomDomainReservedError,
    CustomDomainTakenError,
    StoreNameInvalidError,
    StoreSlugInvalidError,
    StoreSlugReservedError,
)
from apps.tenants.models import StoreDomain, Tenant

RESERVED_TENANT_SLUGS: set[str] = {
    "admin",
    "api",
    "www",
    "dashboard",
    "store",
}

RESERVED_CUSTOM_DOMAINS: set[str] = {
    "localhost",
    "example.com",
    "example.net",
    "example.org",
}

RESERVED_CUSTOM_DOMAIN_SUFFIXES: tuple[str, ...] = (
    ".local",
    ".internal",
    ".invalid",
    ".test",
)

_SUBDOMAIN_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?$")
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z]{2,63}$"
)


def validate_store_name(raw: str) -> str:
    name = (raw or "").strip()
    if not name:
        raise StoreNameInvalidError("Store name is required.")
    if len(name) > 200:
        raise StoreNameInvalidError("Store name must be 200 characters or fewer.")
    return name


def normalize_tenant_slug(raw: str) -> str:
    return (raw or "").strip().lower()


def normalize_slug(raw: str) -> str:
    return normalize_tenant_slug(raw)


def validate_tenant_slug(raw: str) -> str:
    slug = normalize_tenant_slug(raw)
    if not slug:
        raise StoreSlugInvalidError("Store slug is required.")
    if slug in RESERVED_TENANT_SLUGS:
        raise StoreSlugReservedError("This store slug is reserved.")
    if len(slug) > 63:
        raise StoreSlugInvalidError("Store slug must be 63 characters or fewer.")
    if not _SUBDOMAIN_SLUG_RE.match(slug):
        raise StoreSlugInvalidError(
            "Store slug must be a valid subdomain label (letters/numbers/hyphens, no leading/trailing hyphen)."
        )
    return slug


def normalize_hex_color(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if not value.startswith("#"):
        value = f"#{value}"
    return value.lower()


def validate_hex_color(raw: str) -> str:
    value = normalize_hex_color(raw)
    if not value:
        return ""
    if not _HEX_COLOR_RE.match(value):
        raise StoreSlugInvalidError("Brand color must be a valid hex color like #1d4ed8.")
    return value


def normalize_custom_domain(raw: str) -> str:
    return (raw or "").strip().lower().rstrip(".")


def normalize_domain(raw: str) -> str:
    return normalize_custom_domain(raw)


def validate_custom_domain(raw: str) -> str:
    domain = normalize_custom_domain(raw)
    if not domain:
        return ""
    return validate_domain_format(domain)


def validate_domain_format(raw: str) -> str:
    domain = normalize_custom_domain(raw)
    if not domain:
        raise CustomDomainInvalidError("Custom domain is required.")
    if "://" in domain or "/" in domain or " " in domain:
        raise CustomDomainInvalidError("Custom domain must be a hostname only (no scheme/path/spaces).")
    if not _DOMAIN_RE.match(domain):
        raise CustomDomainInvalidError("Custom domain must be a valid hostname like example.com.")
    return domain


def prevent_reserved_domains(domain: str) -> None:
    normalized = normalize_custom_domain(domain)
    if normalized in RESERVED_CUSTOM_DOMAINS:
        raise CustomDomainReservedError("This domain is reserved.")
    if any(normalized.endswith(suffix) for suffix in RESERVED_CUSTOM_DOMAIN_SUFFIXES):
        raise CustomDomainReservedError("This domain suffix is reserved.")


def prevent_platform_domain_usage(domain: str, *, base_domain: str, blocked_domains: list[str] | None = None) -> None:
    normalized = normalize_custom_domain(domain)
    base = normalize_custom_domain(base_domain).lstrip(".")
    if base and (normalized == base or normalized.endswith(f".{base}")):
        raise CustomDomainNotAllowedError("Platform domains cannot be used as custom domains.")

    for blocked in blocked_domains or []:
        blocked_norm = normalize_custom_domain(blocked).lstrip(".")
        if blocked_norm and (normalized == blocked_norm or normalized.endswith(f".{blocked_norm}")):
            raise CustomDomainNotAllowedError("This domain is not allowed.")


def ensure_domain_not_taken(domain: str, *, tenant_id: int | None = None) -> None:
    normalized = normalize_custom_domain(domain)
    if not normalized:
        raise CustomDomainInvalidError("Custom domain is required.")

    taken = StoreDomain.objects.filter(domain=normalized)
    if tenant_id is not None:
        taken = taken.exclude(tenant_id=tenant_id)
    if taken.exists():
        raise CustomDomainTakenError("This domain is already connected to another store.")

    legacy = Tenant.objects.filter(domain=normalized)
    if tenant_id is not None:
        legacy = legacy.exclude(id=tenant_id)
    if legacy.exists():
        raise CustomDomainTakenError("This domain is already connected to another store.")


def ensure_one_active_domain_per_store(*, tenant_id: int, allow_domain_id: int | None = None) -> None:
    qs = StoreDomain.objects.filter(
        tenant_id=tenant_id,
        status__in=(StoreDomain.STATUS_ACTIVE, StoreDomain.STATUS_SSL_ACTIVE),
    )
    if allow_domain_id is not None:
        qs = qs.exclude(id=allow_domain_id)
    if qs.exists():
        raise CustomDomainNotAllowedError("Only one active custom domain is allowed per store.")

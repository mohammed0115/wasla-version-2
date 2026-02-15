from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser

from tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from tenants.domain.policies import (
    prevent_platform_domain_usage,
    prevent_reserved_domains,
    validate_custom_domain,
)
from tenants.models import StoreDomain, Tenant


@dataclass(frozen=True)
class ValidateCustomDomainCommand:
    user: AbstractBaseUser
    tenant: Tenant
    custom_domain: str


@dataclass(frozen=True)
class ValidateCustomDomainResult:
    normalized_domain: str
    is_conflict: bool


class ValidateCustomDomainUseCase:
    @staticmethod
    def execute(cmd: ValidateCustomDomainCommand) -> ValidateCustomDomainResult:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=cmd.user, tenant=cmd.tenant)

        normalized = validate_custom_domain(cmd.custom_domain)
        if not normalized:
            return ValidateCustomDomainResult(normalized_domain="", is_conflict=False)

        prevent_reserved_domains(normalized)
        prevent_platform_domain_usage(
            normalized,
            base_domain=getattr(settings, "WASSLA_BASE_DOMAIN", ""),
            blocked_domains=getattr(settings, "CUSTOM_DOMAIN_BLOCKED_DOMAINS", []),
        )

        conflict = StoreDomain.objects.filter(domain=normalized).exclude(tenant=cmd.tenant).exists()
        if not conflict:
            conflict = Tenant.objects.filter(domain=normalized).exclude(id=cmd.tenant.id).exists()
        return ValidateCustomDomainResult(normalized_domain=normalized, is_conflict=conflict)

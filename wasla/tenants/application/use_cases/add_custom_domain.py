from __future__ import annotations

from dataclasses import dataclass
from secrets import token_urlsafe

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from tenants.domain.errors import CustomDomainTakenError
from tenants.domain.policies import (
    ensure_domain_not_taken,
    prevent_platform_domain_usage,
    prevent_reserved_domains,
    validate_domain_format,
)
from tenants.models import StoreDomain, Tenant
from tenants.services.audit_service import TenantAuditService


@dataclass(frozen=True)
class AddCustomDomainCommand:
    user: AbstractBaseUser
    tenant: Tenant
    domain: str


@dataclass(frozen=True)
class AddCustomDomainResult:
    store_domain: StoreDomain
    created: bool


class AddCustomDomainUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: AddCustomDomainCommand) -> AddCustomDomainResult:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=cmd.user, tenant=cmd.tenant)

        normalized = validate_domain_format(cmd.domain)
        prevent_reserved_domains(normalized)
        prevent_platform_domain_usage(
            normalized,
            base_domain=getattr(settings, "WASSLA_BASE_DOMAIN", ""),
            blocked_domains=getattr(settings, "CUSTOM_DOMAIN_BLOCKED_DOMAINS", []),
        )

        existing = StoreDomain.objects.filter(domain=normalized).select_for_update().first()
        if existing:
            if existing.tenant_id != cmd.tenant.id:
                raise CustomDomainTakenError("This domain is already connected to another store.")

            if existing.status in (StoreDomain.STATUS_DISABLED, StoreDomain.STATUS_FAILED):
                existing.status = StoreDomain.STATUS_PENDING_VERIFICATION
                existing.verification_token = token_urlsafe(32)
                existing.verified_at = None
                existing.ssl_cert_path = ""
                existing.ssl_key_path = ""
                existing.last_check_at = None
                existing.save(
                    update_fields=[
                        "status",
                        "verification_token",
                        "verified_at",
                        "ssl_cert_path",
                        "ssl_key_path",
                        "last_check_at",
                    ]
                )
            return AddCustomDomainResult(store_domain=existing, created=False)

        ensure_domain_not_taken(normalized, tenant_id=cmd.tenant.id)

        store_domain = StoreDomain.objects.create(
            tenant=cmd.tenant,
            domain=normalized,
            status=StoreDomain.STATUS_PENDING_VERIFICATION,
            verification_token=token_urlsafe(32),
        )

        TenantAuditService.record_action(
            cmd.tenant,
            "custom_domain_added",
            actor=getattr(cmd.user, "username", "user"),
            details=f"Custom domain {normalized} added.",
            metadata={"domain": normalized},
        )

        return AddCustomDomainResult(store_domain=store_domain, created=True)

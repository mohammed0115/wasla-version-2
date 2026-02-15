from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from tenants.domain.errors import CustomDomainNotAllowedError
from tenants.infrastructure.reverse_proxy import NginxReverseProxyAdapter
from tenants.models import StoreDomain
from tenants.services.audit_service import TenantAuditService
from tenants.services.domain_resolution import invalidate_domain_cache


@dataclass(frozen=True)
class DisableDomainCommand:
    actor: AbstractBaseUser | None
    domain_id: int
    reason: str = ""
    skip_ownership_check: bool = False


class DisableDomainUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: DisableDomainCommand) -> StoreDomain:
        store_domain = (
            StoreDomain.objects.select_for_update()
            .select_related("tenant")
            .filter(id=cmd.domain_id)
            .first()
        )
        if not store_domain:
            raise CustomDomainNotAllowedError("Domain not found.")

        if not cmd.skip_ownership_check:
            if cmd.actor is None:
                raise CustomDomainNotAllowedError("Ownership verification required.")
            EnsureTenantOwnershipPolicy.ensure_is_owner(user=cmd.actor, tenant=store_domain.tenant)

        if store_domain.status == StoreDomain.STATUS_DISABLED:
            return store_domain

        store_domain.status = StoreDomain.STATUS_DISABLED
        store_domain.save(update_fields=["status"])

        if store_domain.tenant.domain == store_domain.domain:
            store_domain.tenant.domain = ""
            store_domain.tenant.save(update_fields=["domain"])

        NginxReverseProxyAdapter.remove_domain_config(store_domain.domain)
        invalidate_domain_cache(store_domain.domain)

        TenantAuditService.record_action(
            store_domain.tenant,
            "custom_domain_disabled",
            actor=getattr(cmd.actor, "username", "system") if cmd.actor else "system",
            details=f"Custom domain {store_domain.domain} disabled.",
            metadata={"domain": store_domain.domain, "reason": cmd.reason},
        )

        return store_domain

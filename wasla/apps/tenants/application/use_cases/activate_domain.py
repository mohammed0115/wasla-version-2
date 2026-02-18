from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils import timezone

from apps.tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from apps.tenants.domain.errors import CustomDomainNotAllowedError, CustomDomainVerificationError
from apps.tenants.domain.policies import ensure_one_active_domain_per_store
from apps.tenants.infrastructure.reverse_proxy import NginxReverseProxyAdapter
from apps.tenants.infrastructure.ssl_manager import SslManagerAdapter
from apps.tenants.models import StoreDomain
from apps.tenants.services.audit_service import TenantAuditService
from apps.tenants.services.domain_resolution import invalidate_domain_cache


@dataclass(frozen=True)
class ActivateDomainCommand:
    actor: AbstractBaseUser | None
    domain_id: int
    skip_ownership_check: bool = False


class ActivateDomainUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: ActivateDomainCommand) -> StoreDomain:
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
            raise CustomDomainNotAllowedError("Domain is disabled.")
        if store_domain.status in (StoreDomain.STATUS_ACTIVE, StoreDomain.STATUS_SSL_ACTIVE):
            return store_domain
        if not store_domain.verified_at:
            raise CustomDomainVerificationError("Domain must be verified before activation.")

        try:
            ensure_one_active_domain_per_store(
                tenant_id=store_domain.tenant_id, allow_domain_id=store_domain.id
            )
        except CustomDomainNotAllowedError:
            previous_active = list(
                StoreDomain.objects.filter(
                    tenant_id=store_domain.tenant_id,
                    status__in=(StoreDomain.STATUS_ACTIVE, StoreDomain.STATUS_SSL_ACTIVE),
                ).exclude(id=store_domain.id)
            )
            if previous_active:
                StoreDomain.objects.filter(id__in=[item.id for item in previous_active]).update(
                    status=StoreDomain.STATUS_DISABLED
                )
                for item in previous_active:
                    NginxReverseProxyAdapter.remove_domain_config(item.domain)
                    invalidate_domain_cache(item.domain)

        ssl_cert_path = store_domain.ssl_cert_path
        ssl_key_path = store_domain.ssl_key_path

        if getattr(settings, "CUSTOM_DOMAIN_SSL_ENABLED", False):
            try:
                cert_result = SslManagerAdapter.issue_certificate(store_domain.domain)
                ssl_cert_path = cert_result.cert_path
                ssl_key_path = cert_result.key_path
            except Exception as exc:
                store_domain.status = StoreDomain.STATUS_FAILED
                store_domain.save(update_fields=["status"])
                raise CustomDomainVerificationError(str(exc)) from exc

        upstream = getattr(settings, "CUSTOM_DOMAIN_NGINX_UPSTREAM", "http://127.0.0.1:8000")
        try:
            NginxReverseProxyAdapter.ensure_domain_config(
                store_domain.domain,
                upstream=upstream,
                ssl_cert_path=ssl_cert_path,
                ssl_key_path=ssl_key_path,
            )
        except Exception as exc:
            store_domain.status = StoreDomain.STATUS_FAILED
            store_domain.save(update_fields=["status"])
            raise CustomDomainVerificationError(str(exc)) from exc

        store_domain.status = StoreDomain.STATUS_SSL_ACTIVE
        store_domain.ssl_cert_path = ssl_cert_path
        store_domain.ssl_key_path = ssl_key_path
        if not store_domain.verified_at:
            store_domain.verified_at = timezone.now()
        store_domain.save(
            update_fields=[
                "status",
                "ssl_cert_path",
                "ssl_key_path",
                "verified_at",
            ]
        )

        store_domain.tenant.domain = store_domain.domain
        store_domain.tenant.save(update_fields=["domain"])
        invalidate_domain_cache(store_domain.domain)

        TenantAuditService.record_action(
            store_domain.tenant,
            "custom_domain_activated",
            actor=getattr(cmd.actor, "username", "system") if cmd.actor else "system",
            details=f"Custom domain {store_domain.domain} activated.",
            metadata={"domain": store_domain.domain},
        )

        return store_domain

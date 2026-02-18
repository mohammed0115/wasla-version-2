from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from apps.tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from apps.tenants.domain.errors import CustomDomainNotAllowedError
from apps.tenants.infrastructure.reverse_proxy import NginxReverseProxyAdapter
from apps.tenants.infrastructure.ssl_manager import SslManagerAdapter
from apps.tenants.models import StoreDomain
from apps.tenants.services.audit_service import TenantAuditService


@dataclass(frozen=True)
class RefreshSSLCertificateCommand:
    actor: AbstractBaseUser | None
    domain_id: int
    skip_ownership_check: bool = False


class RefreshSSLCertificateUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: RefreshSSLCertificateCommand) -> StoreDomain:
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

        if store_domain.status not in (StoreDomain.STATUS_ACTIVE, StoreDomain.STATUS_SSL_ACTIVE):
            raise CustomDomainNotAllowedError("Only active domains can refresh SSL.")

        if getattr(settings, "CUSTOM_DOMAIN_SSL_ENABLED", False):
            cert_result = SslManagerAdapter.issue_certificate(store_domain.domain, renew=True)
            store_domain.ssl_cert_path = cert_result.cert_path
            store_domain.ssl_key_path = cert_result.key_path
            store_domain.save(update_fields=["ssl_cert_path", "ssl_key_path"])

        upstream = getattr(settings, "CUSTOM_DOMAIN_NGINX_UPSTREAM", "http://127.0.0.1:8000")
        NginxReverseProxyAdapter.ensure_domain_config(
            store_domain.domain,
            upstream=upstream,
            ssl_cert_path=store_domain.ssl_cert_path,
            ssl_key_path=store_domain.ssl_key_path,
        )

        TenantAuditService.record_action(
            store_domain.tenant,
            "custom_domain_ssl_refreshed",
            actor=getattr(cmd.actor, "username", "system") if cmd.actor else "system",
            details=f"SSL refreshed for {store_domain.domain}.",
            metadata={"domain": store_domain.domain},
        )

        return store_domain

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.db import transaction

from domains.domain.types import DomainProvisionResult
from domains.infrastructure.nginx_generator import NginxConfigGenerator
from domains.infrastructure.ssl_manager import DomainSslManager
from tenants.domain.errors import CustomDomainNotAllowedError, CustomDomainVerificationError
from tenants.models import StoreDomain


@dataclass(frozen=True)
class ProvisionDomainCommand:
    domain_id: int
    renew_ssl: bool = False


class ProvisionDomainUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: ProvisionDomainCommand) -> DomainProvisionResult:
        store_domain = StoreDomain.objects.select_for_update().filter(id=cmd.domain_id).first()
        if not store_domain:
            raise CustomDomainNotAllowedError("Domain not found.")

        if store_domain.status not in (
            StoreDomain.STATUS_VERIFIED,
            StoreDomain.STATUS_SSL_PENDING,
            StoreDomain.STATUS_PENDING_VERIFICATION,
        ):
            raise CustomDomainVerificationError("Domain is not ready for provisioning.")

        ssl_issued = False
        ssl_cert_path = store_domain.ssl_cert_path
        ssl_key_path = store_domain.ssl_key_path

        if getattr(settings, "CUSTOM_DOMAIN_SSL_ENABLED", False):
            cert_result = DomainSslManager.issue(store_domain.domain, renew=cmd.renew_ssl)
            ssl_cert_path = cert_result.cert_path
            ssl_key_path = cert_result.key_path
            ssl_issued = True

        store_domain.ssl_cert_path = ssl_cert_path
        store_domain.ssl_key_path = ssl_key_path
        store_domain.status = StoreDomain.STATUS_SSL_PENDING if ssl_issued else StoreDomain.STATUS_VERIFIED
        store_domain.save(update_fields=["ssl_cert_path", "ssl_key_path", "status"])

        upstream = getattr(settings, "CUSTOM_DOMAIN_NGINX_UPSTREAM", "http://127.0.0.1:8000")
        generator = NginxConfigGenerator()
        content = generator.render(
            domain=store_domain.domain,
            upstream=upstream,
            ssl_cert_path=ssl_cert_path,
            ssl_key_path=ssl_key_path,
            force_https=bool(getattr(settings, "CUSTOM_DOMAIN_FORCE_HTTPS", False)),
        )
        generator.write_config(domain=store_domain.domain, content=content)

        return DomainProvisionResult(
            success=True,
            ssl_issued=ssl_issued,
            nginx_written=True,
            message="Provisioned.",
        )

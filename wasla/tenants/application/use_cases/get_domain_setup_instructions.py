from __future__ import annotations

from dataclasses import dataclass
from secrets import token_urlsafe

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser

from tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from tenants.domain.errors import CustomDomainNotAllowedError
from tenants.domain.policies import normalize_domain
from tenants.models import StoreDomain, Tenant


@dataclass(frozen=True)
class DnsInstruction:
    record_type: str
    host: str
    value: str


@dataclass(frozen=True)
class DomainSetupInstructions:
    domain: StoreDomain
    a_record: DnsInstruction | None
    cname_record: DnsInstruction | None
    verification_path: str
    verification_token: str


@dataclass(frozen=True)
class GetDomainSetupInstructionsCommand:
    user: AbstractBaseUser
    tenant: Tenant
    domain_id: int


class GetDomainSetupInstructionsUseCase:
    @staticmethod
    def execute(cmd: GetDomainSetupInstructionsCommand) -> DomainSetupInstructions:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=cmd.user, tenant=cmd.tenant)

        store_domain = StoreDomain.objects.filter(id=cmd.domain_id, tenant=cmd.tenant).first()
        if not store_domain:
            raise CustomDomainNotAllowedError("Domain not found.")

        if not store_domain.verification_token:
            store_domain.verification_token = token_urlsafe(32)
            store_domain.save(update_fields=["verification_token"])

        server_ip = (getattr(settings, "CUSTOM_DOMAIN_SERVER_IP", "") or "").strip()
        cname_target = (getattr(settings, "CUSTOM_DOMAIN_CNAME_TARGET", "") or "").strip()
        if not cname_target:
            base_domain = normalize_domain(getattr(settings, "WASSLA_BASE_DOMAIN", ""))
            if base_domain:
                cname_target = f"stores.{base_domain}"

        a_record = DnsInstruction(record_type="A", host="@", value=server_ip) if server_ip else None
        cname_record = (
            DnsInstruction(record_type="CNAME", host="@", value=cname_target) if cname_target else None
        )

        verification_path_prefix = getattr(
            settings,
            "CUSTOM_DOMAIN_VERIFICATION_PATH_PREFIX",
            "/.well-known/wassla-domain-verification",
        )
        verification_path = f"{verification_path_prefix.rstrip('/')}/{store_domain.verification_token}"

        return DomainSetupInstructions(
            domain=store_domain,
            a_record=a_record,
            cname_record=cname_record,
            verification_path=verification_path,
            verification_token=store_domain.verification_token,
        )

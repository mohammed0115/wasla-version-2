from __future__ import annotations

from dataclasses import dataclass
from secrets import token_urlsafe

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils import timezone

from apps.tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from apps.tenants.domain.errors import (
    CustomDomainNotAllowedError,
    CustomDomainRateLimitedError,
    CustomDomainVerificationError,
)
from apps.tenants.domain.policies import normalize_domain
from apps.tenants.infrastructure.dns_resolver import DnsResolverAdapter
from apps.tenants.infrastructure.http_challenge import HttpChallengeVerifier
from apps.tenants.infrastructure.reverse_proxy import NginxReverseProxyAdapter
from apps.tenants.models import StoreDomain


@dataclass(frozen=True)
class VerifyDomainOwnershipCommand:
    actor: AbstractBaseUser | None
    domain_id: int
    activate_on_success: bool = True
    skip_ownership_check: bool = False


@dataclass(frozen=True)
class VerifyDomainOwnershipResult:
    verified: bool
    activated: bool
    dns_ok: bool
    http_ok: bool
    message: str = ""


class VerifyDomainOwnershipUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: VerifyDomainOwnershipCommand) -> VerifyDomainOwnershipResult:
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
            return VerifyDomainOwnershipResult(
                verified=True,
                activated=True,
                dns_ok=True,
                http_ok=True,
                message="Domain already active.",
            )

        now = timezone.now()
        min_interval = int(getattr(settings, "CUSTOM_DOMAIN_VERIFY_MIN_INTERVAL_SECONDS", 30) or 30)
        if store_domain.last_check_at and (now - store_domain.last_check_at).total_seconds() < min_interval:
            raise CustomDomainRateLimitedError("Please wait before retrying verification.")

        if not store_domain.verification_token:
            store_domain.verification_token = token_urlsafe(32)

        store_domain.status = StoreDomain.STATUS_VERIFYING
        store_domain.last_check_at = now
        store_domain.save(update_fields=["status", "last_check_at", "verification_token"])

        expected_ip = (getattr(settings, "CUSTOM_DOMAIN_SERVER_IP", "") or "").strip()
        expected_ips = [expected_ip] if expected_ip else []

        cname_target = (getattr(settings, "CUSTOM_DOMAIN_CNAME_TARGET", "") or "").strip()
        if not cname_target:
            base_domain = normalize_domain(getattr(settings, "WASSLA_BASE_DOMAIN", ""))
            if base_domain:
                cname_target = f"stores.{base_domain}"

        dns_ok = DnsResolverAdapter.matches_expected(
            store_domain.domain,
            expected_a=expected_ips,
            expected_cname=cname_target,
        )

        provisioning_mode = (getattr(settings, "DOMAIN_PROVISIONING_MODE", "manual") or "manual").lower()
        if provisioning_mode == "legacy":
            upstream = getattr(settings, "CUSTOM_DOMAIN_NGINX_UPSTREAM", "http://127.0.0.1:8000")
            try:
                NginxReverseProxyAdapter.ensure_domain_config(
                    store_domain.domain,
                    upstream=upstream,
                    ssl_cert_path="",
                    ssl_key_path="",
                )
            except Exception:
                store_domain.status = StoreDomain.STATUS_FAILED
                store_domain.save(update_fields=["status"])
                return VerifyDomainOwnershipResult(
                    verified=False,
                    activated=False,
                    dns_ok=dns_ok,
                    http_ok=False,
                    message="Nginx configuration failed.",
                )

        verification_path_prefix = getattr(
            settings,
            "CUSTOM_DOMAIN_VERIFICATION_PATH_PREFIX",
            "/.well-known/wassla-domain-verification",
        )
        http_result = HttpChallengeVerifier.verify(
            domain=store_domain.domain,
            token=store_domain.verification_token,
            path_prefix=verification_path_prefix,
            timeout_seconds=int(getattr(settings, "CUSTOM_DOMAIN_HTTP_TIMEOUT_SECONDS", 5) or 5),
        )
        http_ok = http_result.ok

        if not dns_ok or not http_ok:
            store_domain.status = StoreDomain.STATUS_FAILED
            store_domain.save(update_fields=["status"])
            return VerifyDomainOwnershipResult(
                verified=False,
                activated=False,
                dns_ok=dns_ok,
                http_ok=http_ok,
                message="Verification failed. Check DNS and HTTP challenge.",
            )

        store_domain.verified_at = now
        store_domain.status = StoreDomain.STATUS_VERIFIED
        store_domain.save(update_fields=["verified_at", "status"])

        if cmd.activate_on_success and provisioning_mode == "legacy":
            from apps.tenants.application.use_cases.activate_domain import (  # local import
                ActivateDomainCommand,
                ActivateDomainUseCase,
            )

            try:
                ActivateDomainUseCase.execute(
                    ActivateDomainCommand(
                        actor=cmd.actor,
                        domain_id=store_domain.id,
                        skip_ownership_check=cmd.skip_ownership_check,
                    )
                )
            except Exception as exc:
                store_domain.status = StoreDomain.STATUS_FAILED
                store_domain.save(update_fields=["status"])
                raise CustomDomainVerificationError(str(exc)) from exc

            return VerifyDomainOwnershipResult(
                verified=True,
                activated=True,
                dns_ok=True,
                http_ok=True,
                message="Domain verified and activated.",
            )

        return VerifyDomainOwnershipResult(
            verified=True,
            activated=False,
            dns_ok=True,
            http_ok=True,
            message="Domain verified. Activation pending.",
        )

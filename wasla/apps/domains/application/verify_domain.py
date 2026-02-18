from __future__ import annotations

from dataclasses import dataclass
from secrets import token_urlsafe

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.domains.domain.policies import expected_cname
from apps.domains.domain.types import DomainVerificationResult
from apps.domains.infrastructure.dns_verifier import DomainDnsVerifier
from apps.domains.infrastructure.http_verifier import DomainHttpVerifier
from apps.tenants.domain.errors import CustomDomainNotAllowedError, CustomDomainRateLimitedError
from apps.tenants.models import StoreDomain


@dataclass(frozen=True)
class VerifyDomainCommand:
    domain_id: int


class VerifyDomainUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: VerifyDomainCommand) -> DomainVerificationResult:
        store_domain = StoreDomain.objects.select_for_update().filter(id=cmd.domain_id).first()
        if not store_domain:
            raise CustomDomainNotAllowedError("Domain not found.")

        if store_domain.status in (StoreDomain.STATUS_SSL_ACTIVE, StoreDomain.STATUS_ACTIVE):
            return DomainVerificationResult(verified=True, dns_ok=True, http_ok=True, message="Already active.")

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
        dns_ok = DomainDnsVerifier.matches(
            store_domain.domain,
            expected_a=expected_ips,
            expected_cname=expected_cname(),
        )

        verification_path_prefix = getattr(
            settings,
            "CUSTOM_DOMAIN_VERIFICATION_PATH_PREFIX",
            "/.well-known/wassla-domain-verification",
        )
        http_result = DomainHttpVerifier.verify(
            domain=store_domain.domain,
            token=store_domain.verification_token,
            path_prefix=verification_path_prefix,
            timeout_seconds=int(getattr(settings, "CUSTOM_DOMAIN_HTTP_TIMEOUT_SECONDS", 5) or 5),
        )
        http_ok = http_result.ok

        if not dns_ok or not http_ok:
            store_domain.status = StoreDomain.STATUS_FAILED
            store_domain.save(update_fields=["status"])
            return DomainVerificationResult(
                verified=False,
                dns_ok=dns_ok,
                http_ok=http_ok,
                message="Verification failed.",
            )

        store_domain.verified_at = now
        store_domain.status = StoreDomain.STATUS_VERIFIED
        store_domain.save(update_fields=["verified_at", "status"])

        return DomainVerificationResult(
            verified=True,
            dns_ok=True,
            http_ok=True,
            message="Domain verified.",
        )

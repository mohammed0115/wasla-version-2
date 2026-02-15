from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from tenants.domain.errors import CustomDomainNotAllowedError, CustomDomainVerificationError
from tenants.domain.policies import normalize_domain


@dataclass(frozen=True)
class SslCertificateResult:
    cert_path: str
    key_path: str


class SslManagerAdapter:
    @staticmethod
    def issue_certificate(domain: str, *, renew: bool = False) -> SslCertificateResult:
        normalized = normalize_domain(domain)
        if not normalized:
            raise CustomDomainVerificationError("Invalid domain for SSL issuance.")

        if not getattr(settings, "CUSTOM_DOMAIN_SSL_ENABLED", False):
            raise CustomDomainNotAllowedError("SSL provisioning is disabled.")

        certbot_cmd = getattr(settings, "CUSTOM_DOMAIN_CERTBOT_CMD", "certbot")
        email = getattr(settings, "CUSTOM_DOMAIN_CERTBOT_EMAIL", "")
        mode = getattr(settings, "CUSTOM_DOMAIN_CERTBOT_MODE", "http-01")
        webroot = getattr(settings, "CUSTOM_DOMAIN_CERTBOT_WEBROOT", "")

        cmd = [
            certbot_cmd,
            "certonly",
            "--non-interactive",
            "--agree-tos",
            "-d",
            normalized,
        ]
        if email:
            cmd += ["--email", email]
        else:
            cmd += ["--register-unsafely-without-email"]

        if mode == "dns-01":
            cmd += ["--manual", "--preferred-challenges", "dns", "--manual-public-ip-logging-ok"]
            auth_hook = getattr(settings, "CUSTOM_DOMAIN_CERTBOT_DNS_AUTH_HOOK", "")
            cleanup_hook = getattr(settings, "CUSTOM_DOMAIN_CERTBOT_DNS_CLEANUP_HOOK", "")
            if auth_hook:
                cmd += ["--manual-auth-hook", auth_hook]
            if cleanup_hook:
                cmd += ["--manual-cleanup-hook", cleanup_hook]
        else:
            if not webroot:
                raise CustomDomainNotAllowedError("CUSTOM_DOMAIN_CERTBOT_WEBROOT is required for HTTP-01 mode.")
            cmd += ["--webroot", "-w", webroot]

        if renew:
            cmd.append("--force-renewal")

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:  # pragma: no cover
            raise CustomDomainVerificationError(
                f"Certbot failed: {exc.stderr or exc.stdout or str(exc)}"
            ) from exc

        base_dir = Path(getattr(settings, "CUSTOM_DOMAIN_CERTS_DIR", "/etc/letsencrypt/live"))
        cert_path = str(base_dir / normalized / "fullchain.pem")
        key_path = str(base_dir / normalized / "privkey.pem")

        return SslCertificateResult(cert_path=cert_path, key_path=key_path)

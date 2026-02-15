from __future__ import annotations

from tenants.infrastructure.ssl_manager import SslManagerAdapter, SslCertificateResult


class DomainSslManager:
    @staticmethod
    def issue(domain: str, *, renew: bool = False) -> SslCertificateResult:
        return SslManagerAdapter.issue_certificate(domain, renew=renew)

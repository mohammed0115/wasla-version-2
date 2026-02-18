from __future__ import annotations

from typing import Iterable

from apps.tenants.infrastructure.dns_resolver import DnsResolverAdapter


class DomainDnsVerifier:
    @staticmethod
    def matches(domain: str, *, expected_a: Iterable[str] | None = None, expected_cname: str | None = None) -> bool:
        return DnsResolverAdapter.matches_expected(
            domain,
            expected_a=expected_a,
            expected_cname=expected_cname,
        )

from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Iterable

from django.conf import settings
from django.core.cache import cache

from tenants.domain.policies import normalize_domain


try:  # optional dependency
    import dns.resolver  # type: ignore
except Exception:  # pragma: no cover
    dns = None


@dataclass(frozen=True)
class DnsLookupResult:
    a_records: tuple[str, ...]
    cname: str | None


class DnsResolverAdapter:
    @staticmethod
    def lookup(domain: str) -> DnsLookupResult:
        normalized = normalize_domain(domain)
        if not normalized:
            return DnsLookupResult(a_records=(), cname=None)

        cache_seconds = int(getattr(settings, "CUSTOM_DOMAIN_DNS_CACHE_SECONDS", 300) or 300)
        cache_key = f"dns_lookup:{normalized}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        a_records = tuple(DnsResolverAdapter._resolve_a_records(normalized))
        cname = DnsResolverAdapter._resolve_cname(normalized)

        result = DnsLookupResult(a_records=a_records, cname=cname)
        cache.set(cache_key, result, cache_seconds)
        return result

    @staticmethod
    def matches_expected(
        domain: str,
        *,
        expected_a: Iterable[str] | None = None,
        expected_cname: str | None = None,
    ) -> bool:
        expected_a = [item.strip() for item in (expected_a or []) if item and item.strip()]
        expected_cname = normalize_domain(expected_cname or "")

        lookup = DnsResolverAdapter.lookup(domain)
        if expected_a and any(record in expected_a for record in lookup.a_records):
            return True
        if expected_cname and lookup.cname and normalize_domain(lookup.cname) == expected_cname:
            return True
        return False

    @staticmethod
    def _resolve_a_records(domain: str) -> list[str]:
        if dns:
            try:
                answers = dns.resolver.resolve(domain, "A")
                return [answer.to_text() for answer in answers]
            except Exception:
                return []

        try:
            _, _, ips = socket.gethostbyname_ex(domain)
            return list(ips or [])
        except Exception:
            return []

    @staticmethod
    def _resolve_cname(domain: str) -> str | None:
        if not dns:
            return None
        try:
            answers = dns.resolver.resolve(domain, "CNAME")
            for answer in answers:
                return str(answer.target).rstrip(".")
        except Exception:
            return None
        return None

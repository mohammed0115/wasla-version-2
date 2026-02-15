from __future__ import annotations

from django.conf import settings

from tenants.domain.policies import normalize_domain


def expected_cname() -> str:
    cname_target = (getattr(settings, "CUSTOM_DOMAIN_CNAME_TARGET", "") or "").strip()
    if cname_target:
        return normalize_domain(cname_target)
    base_domain = normalize_domain(getattr(settings, "WASSLA_BASE_DOMAIN", ""))
    return f"stores.{base_domain}" if base_domain else ""

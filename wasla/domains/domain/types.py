from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainVerificationResult:
    verified: bool
    dns_ok: bool
    http_ok: bool
    message: str


@dataclass(frozen=True)
class DomainProvisionResult:
    success: bool
    ssl_issued: bool
    nginx_written: bool
    message: str

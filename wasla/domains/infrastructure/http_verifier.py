from __future__ import annotations

from tenants.infrastructure.http_challenge import HttpChallengeVerifier


class DomainHttpVerifier:
    @staticmethod
    def verify(*, domain: str, token: str, path_prefix: str, timeout_seconds: int = 5):
        return HttpChallengeVerifier.verify(
            domain=domain,
            token=token,
            path_prefix=path_prefix,
            timeout_seconds=timeout_seconds,
        )

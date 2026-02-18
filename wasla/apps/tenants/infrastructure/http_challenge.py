from __future__ import annotations

from dataclasses import dataclass
from urllib.request import Request, urlopen

from apps.tenants.domain.policies import normalize_domain


@dataclass(frozen=True)
class HttpChallengeResult:
    ok: bool
    status_code: int | None = None
    body: str | None = None


class HttpChallengeVerifier:
    @staticmethod
    def verify(*, domain: str, token: str, path_prefix: str, timeout_seconds: int = 5) -> HttpChallengeResult:
        normalized = normalize_domain(domain)
        if not normalized or not token:
            return HttpChallengeResult(ok=False, status_code=None, body=None)

        url = f"http://{normalized}{path_prefix.rstrip('/')}/{token}"
        req = Request(url, method="GET")
        try:
            with urlopen(req, timeout=timeout_seconds) as resp:
                body = (resp.read() or b"").decode("utf-8", errors="ignore").strip()
                ok = body == token
                return HttpChallengeResult(ok=ok, status_code=resp.status, body=body)
        except Exception:
            return HttpChallengeResult(ok=False, status_code=None, body=None)

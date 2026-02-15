from __future__ import annotations

import re
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from django.utils.deprecation import MiddlewareMixin


@dataclass(frozen=True)
class RateLimitRule:
    key: str
    pattern: str
    methods: tuple[str, ...]
    limit: int
    window: int
    message_key: str

    def matches(self, path: str, method: str) -> bool:
        if method.upper() not in self.methods:
            return False
        return re.search(self.pattern, path) is not None


class RateLimitMiddleware(MiddlewareMixin):
    def process_request(self, request):
        rules = _load_rules()
        path = request.path or ""
        method = request.method or "GET"

        for rule in rules:
            if rule.matches(path, method):
                ident = _client_identifier(request, rule.key)
                cache_key = f"rl:{rule.key}:{ident}"
                count = cache.get(cache_key)
                if count is None:
                    cache.set(cache_key, 1, timeout=rule.window)
                    return None
                if count >= rule.limit:
                    return _rate_limited_response(request, rule.message_key, rule.window)
                cache.set(cache_key, count + 1, timeout=rule.window)
                return None
        return None


def _load_rules() -> list[RateLimitRule]:
    raw = getattr(settings, "SECURITY_RATE_LIMITS", [])
    rules: list[RateLimitRule] = []
    for item in raw:
        rules.append(
            RateLimitRule(
                key=item["key"],
                pattern=item["pattern"],
                methods=tuple(item.get("methods", ["POST"])),
                limit=int(item.get("limit", 10)),
                window=int(item.get("window", 60)),
                message_key=item.get("message_key", "rate_limited"),
            )
        )
    return rules


def _client_identifier(request, prefix: str) -> str:
    tenant_id = getattr(getattr(request, "tenant", None), "id", None)
    user_id = request.user.id if getattr(request, "user", None) and request.user.is_authenticated else None
    ip = request.META.get("REMOTE_ADDR", "unknown")
    return f"{prefix}:{tenant_id or 'na'}:{user_id or 'anon'}:{ip}"


def _rate_limited_response(request, message_key: str, window: int):
    retry_after = str(window)
    if request.path.startswith("/api/"):
        resp = JsonResponse({"success": False, "data": None, "errors": [message_key]}, status=429)
    else:
        resp = HttpResponse(message_key, status=429, content_type="text/plain")
    resp["Retry-After"] = retry_after
    return resp

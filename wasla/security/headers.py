from __future__ import annotations

from django.conf import settings


def build_security_headers() -> dict[str, str]:
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "Referrer-Policy": "same-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }

    csp = build_csp()
    if csp:
        headers["Content-Security-Policy"] = csp

    hsts_seconds = int(getattr(settings, "SECURE_HSTS_SECONDS", 0) or 0)
    if hsts_seconds > 0 and bool(getattr(settings, "SECURE_SSL_REDIRECT", False)):
        headers["Strict-Transport-Security"] = f"max-age={hsts_seconds}; includeSubDomains"

    return headers


def build_csp() -> str:
    if not getattr(settings, "SECURITY_CSP_ENABLED", True):
        return ""

    script_src = ["'self'", "https://cdn.jsdelivr.net", "'unsafe-inline'"]
    style_src = ["'self'", "https://cdn.jsdelivr.net", "'unsafe-inline'"]
    img_src = ["'self'", "data:"]
    font_src = ["'self'", "https://cdn.jsdelivr.net", "data:"]
    connect_src = ["'self'"]

    directives = {
        "default-src": ["'self'"],
        "script-src": script_src,
        "style-src": style_src,
        "img-src": img_src,
        "font-src": font_src,
        "connect-src": connect_src,
        "frame-ancestors": ["'self'"],
    }

    return "; ".join([f"{k} {' '.join(v)}" for k, v in directives.items()])

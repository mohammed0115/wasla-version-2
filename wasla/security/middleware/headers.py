from __future__ import annotations

from django.utils.deprecation import MiddlewareMixin

from security.headers import build_security_headers


class SecurityHeadersMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        headers = build_security_headers()
        for key, value in headers.items():
            response[key] = value
        return response

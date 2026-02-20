from __future__ import annotations


class AdminPortalSecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/admin-portal/"):
            response["X-Frame-Options"] = "DENY"
            response["Cache-Control"] = "no-store"
            response["Referrer-Policy"] = "same-origin"
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response

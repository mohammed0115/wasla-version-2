from __future__ import annotations

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render


class FriendlyErrorsMiddleware:
    """Render friendly error pages for user-facing flows (even in DEBUG)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
        except PermissionDenied:
            if self._should_handle(request):
                return render(request, "403.html", status=403)
            raise
        except Http404:
            if self._should_handle(request):
                return render(request, "404.html", status=404)
            raise
        return response

    @staticmethod
    def _should_handle(request) -> bool:
        if not getattr(settings, "DEBUG", False):
            return False
        path = (request.path or "").lower()
        if path.startswith("/admin-portal/") or path.startswith("/admin/") or path.startswith("/api/"):
            return False
        return True

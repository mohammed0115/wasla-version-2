from __future__ import annotations


class PermissionCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request._rbac_permission_codes = None
        request._rbac_membership = None
        return self.get_response(request)

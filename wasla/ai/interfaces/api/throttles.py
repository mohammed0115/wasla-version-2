from rest_framework.throttling import ScopedRateThrottle


class TenantScopedRateThrottle(ScopedRateThrottle):
    def get_cache_key(self, request, view):
        tenant = getattr(request, "tenant", None)
        if tenant and getattr(tenant, "id", None):
            ident = f"tenant:{tenant.id}"
            scope = self.get_scope(view)
            return self.cache_format % {"scope": scope, "ident": ident}
        return super().get_cache_key(request, view)

"""
Tenant-aware API authentication for Django REST Framework.

Extracts tenant context from JWT tokens, headers, or session.
Validates that requests include valid tenant resolution.
"""

from __future__ import annotations

import logging
from typing import Optional

from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


class TenantTokenAuth(TokenAuthentication):
    """
    Token-based authentication that validates tenant context.
    
    Extracts tenant from:
    1. X-Tenant header
    2. X-Tenant-ID header
    3. JWT token claims
    4. Request.tenant (resolved by middleware)
    
    Raises:
    - AuthenticationFailed: If token is invalid
    - PermissionDenied: If tenant mismatch
    """

    keyword = 'Bearer'

    def authenticate(self, request):
        """
        Authenticate request and optionally validate tenant.
        
        Returns (user, tenant) tuple or None if not authenticated.
        """
        # Try to get token-based auth
        auth_result = super().authenticate(request)
        if auth_result is None:
            return None

        user, auth = auth_result
        
        # Validate tenant context exists
        tenant = self._resolve_tenant(request)
        if not tenant:
            raise AuthenticationFailed("Tenant context required")
        
        # Attach tenant to request if not already attached
        if not hasattr(request, 'tenant') or request.tenant is None:
            request.tenant = tenant
        
        return (user, auth)

    def authenticate_header(self, request):
        """Return auth header for WWW-Authenticate response."""
        return f'{self.keyword} realm="api"'

    def _resolve_tenant(self, request) -> Optional[Tenant]:
        """
        Resolve tenant from request in priority order.
        
        Priority:
        1. X-Tenant or X-Tenant-ID header (ID or slug)
        2. request.tenant (set by middleware)
        3. Session store_id
        
        Returns:
            Tenant object or None
        """
        # Check headers first (explicit tenant override)
        tenant_header = (
            request.headers.get('X-Tenant') or
            request.headers.get('X-Tenant-ID') or
            request.headers.get('X-Tenant-Slug')
        )

        if tenant_header:
            return self._get_tenant_by_header(tenant_header)

        # Check middleware-resolved tenant (second priority)
        if hasattr(request, 'tenant') and request.tenant:
            return request.tenant

        # Check session (third priority)
        store_id = request.session.get('store_id')
        if store_id:
            try:
                store_id = int(store_id)
                return Tenant.objects.get(id=store_id, is_active=True)
            except (ValueError, TypeError, Tenant.DoesNotExist):
                pass

        return None

    def _get_tenant_by_header(self, header_value: str) -> Optional[Tenant]:
        """
        Get tenant from header value (ID or slug).
        
        Args:
            header_value: Tenant ID or slug from header
        
        Returns:
            Tenant object or None
        """
        header_value = (header_value or '').strip()
        if not header_value:
            return None

        # Try parsing as integer ID first
        try:
            tenant_id = int(header_value)
            return Tenant.objects.get(id=tenant_id, is_active=True)
        except (ValueError, TypeError, Tenant.DoesNotExist):
            pass

        # Try slug lookup
        try:
            return Tenant.objects.get(slug=header_value, is_active=True)
        except Tenant.DoesNotExist:
            pass

        return None

    def get_tenant_id(self, request) -> Optional[int]:
        """
        Extract tenant ID from request.
        
        Used in ViewSet.get_queryset() to filter by tenant.
        
        Args:
            request: Django request object
        
        Returns:
            Tenant ID or None
        """
        tenant = getattr(request, 'tenant', None)
        if tenant and hasattr(tenant, 'id'):
            return tenant.id
        return None


class TenantPermission:
    """
    Mixin for ViewSets to enforce tenant-scoped queries.
    
    Usage:
        class MyViewSet(TenantPermission, viewsets.ModelViewSet):
            def get_queryset(self):
                return super().get_queryset().filter(tenant=self.request.tenant)
    """

    def get_tenant(self):
        """Get tenant from request."""
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            raise PermissionDenied("Tenant context required")
        return tenant

    def get_tenant_id(self):
        """Get tenant ID from request."""
        return self.get_tenant().id

    def get_filtered_queryset(self, queryset):
        """
        Filter queryset by tenant.
        
        Args:
            queryset: Base queryset
        
        Returns:
            Filtered queryset
        """
        tenant = self.get_tenant()
        return queryset.filter(tenant=tenant)


class StrictTenantPermission:
    """
    Strict tenant enforcement - raises error if tenant not found.
    
    Used for sensitive operations that MUST have tenant context.
    """

    def ensure_tenant(self):
        """Verify tenant context exists."""
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            logger.warning(
                f"SECURITY: StrictTenantPermission violation. "
                f"Path: {self.request.path}, User: {self.request.user.id if self.request.user else 'ANON'}"
            )
            raise PermissionDenied("Tenant context is required for this operation")
        return tenant

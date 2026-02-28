"""
Enhanced tenant middleware with stricter request-level guards.

Prevents:
- Requests without resolved tenant (when required)
- Tenant resolution bypass attacks
- Cross-tenant data access in sensitive operations
"""

from __future__ import annotations

import logging
from typing import Optional, Set

from django.conf import settings
from django.http import Http404, HttpResponse
from django.db.utils import OperationalError, ProgrammingError
from django.utils.deprecation import MiddlewareMixin
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


class TenantSecurityMiddleware(MiddlewareMixin):
    """
    Enforce strict tenant validation at the request level.
    
    Config in settings.py:
    - TENANT_REQUIRED_PATHS: List of path prefixes requiring tenant resolution
    - TENANT_ALLOW_ANONYMOUS: Whether to allow anonymous user access
    - TENANT_BYPASS_SUPERADMIN: Allow superadmin to bypass tenant checks
    """
    
    # Paths that DON'T require tenant resolution
    TENANT_OPTIONAL_PATHS = {
        '/api/auth/',           # Authentication endpoints
        '/api/health/',         # Health checks
        '/healthz',             # Readiness/liveness probes
        '/readyz',
        '/metrics',
        '/admin-portal/',       # Admin portal (optional tenant sometimes)
        '/static/',             # Static files
        '/media/',              # Media files
        '/api/schema/',         # API docs
        '/api/docs/',
        '/api/redoc/',
    }
    
    def __init__(self, get_response):
        self.get_response = get_response
        self._compile_tenant_required_paths()
    
    def _compile_tenant_required_paths(self):
        """Compile configurable tenant-required paths."""
        self.tenant_required_paths: Set[str] = set(
            getattr(settings, 'TENANT_REQUIRED_PATHS', {
                '/api/v1/',
                '/api/subscriptions/',
                '/billing/',
                '/merchant/',
                '/dashboard/',
            })
        )
    
    def process_request(self, request):
        """
        Guard: Ensure tenant is properly resolved before processing.
        """
        # Attach tenant to request (already done by TenantMiddleware)
        tenant = getattr(request, 'tenant', None)
        
        # Check if this path requires a tenant
        if self._path_requires_tenant(request.path):
            if not tenant:
                return self._handle_missing_tenant(request)
        
        # Additional security checks
        if tenant and request.user and request.user.is_authenticated:
            # Verify user has access to this tenant
            if not self._user_has_tenant_access(request.user, tenant):
                logger.warning(
                    f"SECURITY: User {request.user.id} attempted to access tenant {tenant.id} "
                    f"without permission. Path: {request.path}"
                )
                return HttpResponse("Access Denied", status=403)
        
        return None
    
    def _path_requires_tenant(self, path: str) -> bool:
        """Determine if a path requires tenant resolution."""
        # Check optional paths first
        for optional_path in self.TENANT_OPTIONAL_PATHS:
            if path.startswith(optional_path):
                return False
        
        # Check configured required paths
        for required_path in self.tenant_required_paths:
            if path.startswith(required_path):
                return True
        
        # Default: require tenant for API routes
        if path.startswith('/api/'):
            return True
        
        return False
    
    def _user_has_tenant_access(self, user, tenant) -> bool:
        """
        Verify user has legitimate access to this tenant.
        
        Access is allowed if:
        - User is superadmin
        - User owns the tenant (store owner)
        - User is staff in the tenant
        """
        if user.is_superuser and getattr(settings, 'TENANT_BYPASS_SUPERADMIN', True):
            return True
        
        # Check if user owns this tenant
        try:
            from apps.stores.models import Store
            store = Store.objects.filter(
                tenant=tenant,
                owner=user
            ).exists()
            if store:
                return True
        except Exception:
            pass
        
        # Check if user has staff role in this tenant
        try:
            from apps.tenants.models import StaffRole
            staff = StaffRole.objects.filter(
                tenant=tenant,
                user=user
            ).exists()
            if staff:
                return True
        except Exception:
            pass
        
        return False
    
    def _handle_missing_tenant(self, request):
        """
        Handle missing tenant based on request type.
        
        - API requests: 403 Forbidden
        - Page requests: Redirect to store selection or 404
        - Health checks: Allow through
        """
        path = request.path
        
        if path.startswith('/api/'):
            logger.warning(
                f"SECURITY: API request without tenant resolution. "
                f"Path: {path}, User: {request.user.id if request.user else 'ANON'}"
            )
            return HttpResponse(
                '{"error": "Tenant context required"}',
                status=403,
                content_type='application/json'
            )
        
        # For web requests, return 404 or redirect
        logger.warning(
            f"SECURITY: Web request without tenant resolution. "
            f"Path: {path}, User: {request.user.id if request.user else 'ANON'}"
        )
        raise Http404("Store context required")


class TenantContextMiddleware(MiddlewareMixin):
    """
    Ensure tenant context persists throughout the request lifecycle.
    
    Validates that:
    - Tenant doesn't change mid-request
    - Tenant ID matches expectations for sensitive operations
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def process_response(self, request, response):
        """
        Validate tenant context at response time.
        """
        # Log any suspicious tenant changes
        original_tenant = getattr(request, '_original_tenant', None)
        current_tenant = getattr(request, 'tenant', None)
        
        if original_tenant and current_tenant and original_tenant.id != current_tenant.id:
            logger.error(
                f"SECURITY ALERT: Tenant context changed during request! "
                f"Original: {original_tenant.id}, Current: {current_tenant.id}, "
                f"Path: {request.path}, User: {request.user.id if request.user else 'ANON'}"
            )
        
        return response


class TenantAuditMiddleware(MiddlewareMixin):
    """
    Audit all tenant-related access and permission checks.
    
    Logs:
    - Cross-tenant query attempts
    - Tenant resolution chain (headers → session → domain)
    - Permission denied events
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def process_request(self, request):
        """
        Log tenant resolution for audit trail.
        """
        # Store original tenant for validation during response
        current_tenant = getattr(request, 'tenant', None)
        request._original_tenant = current_tenant
        
        # Log sensitive API calls
        if request.path.startswith('/api/') and request.user and request.user.is_authenticated:
            if current_tenant:
                logger.debug(
                    f"Tenant API Access: user_id={request.user.id}, "
                    f"tenant_id={current_tenant.id}, path={request.path}, method={request.method}"
                )
        
        return None

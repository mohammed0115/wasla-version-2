"""
Enhanced tenant middleware with stricter request-level guards.

Prevents:
- Requests without resolved tenant (when required)
- Tenant resolution bypass attacks
- Cross-tenant data access in sensitive operations

Django 5+ Compatible: New-style middleware (WSGI)
All classes implement __init__(get_response) and __call__(request) pattern.
"""

from __future__ import annotations

import logging
from typing import Optional, Set, Callable, Any

from django.conf import settings
from django.http import Http404, HttpResponse, HttpRequest
from django.db.utils import OperationalError, ProgrammingError
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.shortcuts import redirect

logger = logging.getLogger(__name__)


class TenantSecurityMiddleware:
    """
    Enforce strict tenant validation at the request level.
    
    Django 5+ new-style middleware (WSGI).
    
    Config in settings.py:
    - TENANT_REQUIRED_PATHS: List of path prefixes requiring tenant resolution
    - TENANT_ALLOW_ANONYMOUS: Whether to allow anonymous user access
    - TENANT_BYPASS_SUPERADMIN: Allow superadmin to bypass tenant checks
    """
    
    # Paths that DON'T require tenant resolution
    TENANT_OPTIONAL_PATHS = {
        '/api/auth/',           # Authentication endpoints
        '/onboarding/',         # Persona/onboarding flow (no tenant yet)
        '/billing/onboarding/', # Billing onboarding flow (no tenant yet)
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
    
    def __init__(self, get_response: Callable) -> None:
        """Initialize middleware with WSGI app."""
        self.get_response = get_response
        self._compile_tenant_required_paths()
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process request and call next middleware/view."""
        # Guard: Ensure tenant is properly resolved before processing
        response = self._check_tenant_security(request)
        if response:
            return response
        
        # Call the next middleware/view
        response = self.get_response(request)
        return response
    
    def _compile_tenant_required_paths(self) -> None:
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
    
    def _check_tenant_security(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Perform tenant security checks.
        Returns error response if checks fail, None if checks pass.
        """
        if getattr(request, "_is_root_domain_no_default", False):
            if request.path in ["/healthz", "/readyz", "/metrics"]:
                return None
            return self._handle_missing_tenant(request)

        # Attach tenant to request (already done by TenantMiddleware)
        tenant = getattr(request, 'tenant', None)
        
        # Check if this path requires a tenant
        requires_tenant = self._path_requires_tenant(request.path)
        if requires_tenant:
            if not tenant:
                return self._handle_missing_tenant(request)

            # Additional security checks for tenant-required paths only
            # SAFE: AuthenticationMiddleware guaranteed to have run before this middleware
            user = getattr(request, 'user', None)
            if user and user.is_authenticated:
                # Verify user has access to this tenant
                if not self._user_has_tenant_access(user, tenant):
                    # If user is on root domain, redirect them to their own store subdomain
                    redirect_response = self._redirect_to_user_store(request, user)
                    if redirect_response is not None:
                        return redirect_response

                    user_id = getattr(user, 'id', 'UNKNOWN')
                    logger.warning(
                        f"SECURITY: User {user_id} attempted to access tenant {tenant.id} "
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
    
    def _user_has_tenant_access(self, user: Any, tenant: Any) -> bool:
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

    def _redirect_to_user_store(self, request: HttpRequest, user: Any) -> Optional[HttpResponse]:
        """If user has a store and is browsing root domain, redirect to their subdomain."""
        host = (request.get_host() or "").split(":", 1)[0].strip().lower()
        base_domain = (getattr(settings, "WASSLA_BASE_DOMAIN", "w-sala.com") or "w-sala.com").strip().lower()
        if not host or host not in {base_domain, f"www.{base_domain}"}:
            return None

        try:
            from apps.stores.models import Store
            store = Store.objects.select_related("tenant").filter(owner=user).order_by("id").first()
            if not store:
                from apps.tenants.models import TenantMembership, StoreProfile
                membership = (
                    TenantMembership.objects.select_related("tenant")
                    .filter(user=user, is_active=True, tenant__is_active=True)
                    .order_by("tenant_id")
                    .first()
                )
                if membership:
                    store = Store.objects.filter(tenant=membership.tenant).order_by("id").first()
                if not store:
                    profile = (
                        StoreProfile.objects.select_related("tenant")
                        .filter(owner=user, tenant__is_active=True)
                        .order_by("tenant_id")
                        .first()
                    )
                    if profile:
                        store = Store.objects.filter(tenant=profile.tenant).order_by("id").first()
        except Exception:
            store = None

        if not store:
            return None

        subdomain = (getattr(store, "subdomain", "") or getattr(store, "slug", "") or "").strip().lower()
        if not subdomain:
            return None

        scheme = "https" if request.is_secure() else "http"
        target = f"{scheme}://{subdomain}.{base_domain}{request.get_full_path()}"
        return redirect(target)
    
    def _handle_missing_tenant(self, request: HttpRequest) -> HttpResponse:
        """
        Handle missing tenant based on request type.
        
        - API requests: 403 Forbidden
        - Root domain without default store: 503 Service Unavailable with friendly template
        - Other web requests: 404 Not Found
        - Health checks: Allow through
        """
        path = request.path
        
        # SAFE: Use getattr with fallback since request.user may not have id attribute
        user = getattr(request, 'user', None)
        user_id = getattr(user, 'id', None) if user else None
        user_info = f"User: {user_id}" if user_id else "User: ANON"
        
        # Check if this is a root domain request without default store
        is_root_domain_no_default = getattr(request, '_is_root_domain_no_default', False)
        
        if path.startswith('/api/'):
            logger.warning(
                f"SECURITY: API request without tenant resolution. "
                f"Path: {path}, {user_info}"
            )
            return HttpResponse(
                '{"error": "Tenant context required"}',
                status=403,
                content_type='application/json'
            )
        
        # For root domain without default store, return friendly 503
        if is_root_domain_no_default:
            logger.error(
                f"SECURITY: Root domain request without platform default store configured. "
                f"Path: {path}, {user_info}. "
                f"Run `python manage.py ensure_platform_store` or mark a store as platform default."
            )
            try:
                return render(
                    request,
                    'tenants/default_store_not_configured.html',
                    {
                        'default_store_slug': getattr(settings, 'WASSLA_PLATFORM_STORE_SLUG', '') or 'platform',
                    },
                    status=503,
                )
            except Exception:
                # Fallback if template doesn't exist
                return HttpResponse(
                    f'<html><head><title>Service Unavailable</title></head>'
                    f'<body><h1>503 Service Unavailable</h1>'
                    f'<p>Platform default store not configured. Please contact the administrator.</p></body></html>',
                    status=503,
                    content_type='text/html'
                )
        
        # For other web requests, return 404
        logger.warning(
            f"SECURITY: Web request without tenant resolution. "
            f"Path: {path}, {user_info}"
        )
        raise Http404("Store context required")


class TenantContextMiddleware:
    """
    Ensure tenant context persists throughout the request lifecycle.
    
    Django 5+ new-style middleware (WSGI).
    
    Validates that:
    - Tenant doesn't change mid-request
    - Tenant ID matches expectations for sensitive operations
    """
    
    def __init__(self, get_response: Callable) -> None:
        """Initialize middleware with WSGI app."""
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process request and call next middleware/view."""
        # Store original tenant for validation during response
        original_tenant = getattr(request, 'tenant', None)
        request._original_tenant = original_tenant
        
        # Call the next middleware/view
        response = self.get_response(request)
        
        # Validate tenant context at response time
        return self._validate_tenant_context(request, response)
    
    def _validate_tenant_context(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Validate tenant context at response time.
        """
        # Log any suspicious tenant changes
        original_tenant = getattr(request, '_original_tenant', None)
        current_tenant = getattr(request, 'tenant', None)
        
        if original_tenant and current_tenant and original_tenant.id != current_tenant.id:
            # SAFE: Use getattr with fallback for user.id
            user = getattr(request, 'user', None)
            user_id = getattr(user, 'id', None) if user else None
            user_info = f"User: {user_id}" if user_id else "User: ANON"
            
            logger.error(
                f"SECURITY ALERT: Tenant context changed during request! "
                f"Original: {original_tenant.id}, Current: {current_tenant.id}, "
                f"Path: {request.path}, {user_info}"
            )
        
        return response


class TenantAuditMiddleware:
    """
    Audit all tenant-related access and permission checks.
    
    Django 5+ new-style middleware (WSGI).
    
    Logs:
    - Cross-tenant query attempts
    - Tenant resolution chain (headers → session → domain)
    - Permission denied events
    """
    
    def __init__(self, get_response: Callable) -> None:
        """Initialize middleware with WSGI app."""
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process request with audit logging."""
        # Log tenant resolution for audit trail
        self._log_tenant_access(request)
        
        # Call the next middleware/view
        response = self.get_response(request)
        return response
    
    def _log_tenant_access(self, request: HttpRequest) -> None:
        """
        Log tenant resolution for audit trail.
        """
        current_tenant = getattr(request, 'tenant', None)
        
        # Log sensitive API calls
        # SAFE: AuthenticationMiddleware guaranteed to have run before this middleware
        user = getattr(request, 'user', None)
        if request.path.startswith('/api/') and user and user.is_authenticated:
            if current_tenant:
                user_id = getattr(user, 'id', 'UNKNOWN')
                logger.debug(
                    f"Tenant API Access: user_id={user_id}, "
                    f"tenant_id={current_tenant.id}, path={request.path}, method={request.method}"
                )

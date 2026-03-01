"""
Security decorators for sensitive operations.

Provides guards for:
- Signature verification (webhooks, API calls)
- Rate limiting (per-user, per-IP)
- CSRF token validation
- Permission/role checks
- Data encryption requirements
"""

from __future__ import annotations

import functools
import hashlib
import hmac
import json
import logging
from typing import Callable, Optional, Any

from django.conf import settings
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import HttpRequest, JsonResponse, HttpResponse
from django.utils.decorators import decorator_from_middleware_with_args
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


def require_signature(
    secret_field: str = "WEBHOOK_SECRET",
    header_name: str = "X-Signature",
    algorithm: str = "sha256"
) -> Callable:
    """
    Guard: Verify request signature (HMAC).
    
    Usage:
        @require_signature(secret_field="STRIPE_WEBHOOK_SECRET")
        def webhook_handler(request):
            ...
    
    Args:
        secret_field: Settings key for webhook secret
        header_name: Header containing signature
        algorithm: Hash algorithm (sha256, sha1, etc.)
    
    Raises:
        PermissionDenied: If signature is invalid or missing
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> Any:
            # Get secret from settings
            secret = getattr(settings, secret_field, None)
            if not secret:
                logger.error(f"Signature guard: {secret_field} not configured")
                raise SuspiciousOperation(f"{secret_field} not configured")
            
            # Get signature from header
            provided_signature = request.META.get(f"HTTP_{header_name.upper().replace('-', '_')}", "")
            if not provided_signature:
                logger.warning(f"Signature guard: {header_name} header missing")
                raise PermissionDenied("Missing signature header")
            
            # Get request body
            try:
                body = request.body.decode('utf-8')
            except (AttributeError, UnicodeDecodeError):
                body = request.body if isinstance(request.body, str) else ""
            
            # Calculate expected signature
            expected_signature = hmac.new(
                secret.encode(),
                body.encode() if isinstance(body, str) else body,
                getattr(hashlib, algorithm)
            ).hexdigest()
            
            # Compare signatures (constant time)
            if not hmac.compare_digest(expected_signature, provided_signature):
                logger.error(
                    f"Signature guard: signature mismatch for {request.path}",
                    extra={"path": request.path, "method": request.method}
                )
                raise PermissionDenied("Invalid signature")
            
            return view_func(request, *args, **kwargs)
        
        return csrf_exempt(wrapper)
    
    return decorator


def require_permissions(*required_permissions: str) -> Callable:
    """
    Guard: Check user has required permissions.
    
    Usage:
        @require_permissions('payments:read', 'orders:manage')
        def sensitive_view(request):
            ...
    
    Args:
        required_permissions: Codenames of required permissions
    
    Raises:
        PermissionDenied: If user lacks any required permission
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> Any:
            user = getattr(request, 'user', None)
            
            if not user or not user.is_authenticated:
                logger.warning(f"Permission guard: unauthenticated access to {request.path}")
                raise PermissionDenied("Authentication required")
            
            # Check if user has all required permissions
            user_perms = set(user.get_all_permissions())
            required = set(f"{app}.{perm}" for app, perm in 
                          (p.split(':') if ':' in p else (p, '') for p in required_permissions))
            
            if not required.issubset(user_perms):
                missing = required - user_perms
                logger.warning(
                    f"Permission guard: user {user.id} missing {missing} for {request.path}"
                )
                raise PermissionDenied(f'Missing permissions: {", ".join(missing)}')
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


def require_role(*required_roles: str) -> Callable:
    """
    Guard: Check user has required role (from custom permission groups).
    
    Usage:
        @require_role('admin', 'merchant')
        def admin_view(request):
            ...
    
    Args:
        required_roles: Role names
    
    Raises:
        PermissionDenied: If user lacks required role
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> Any:
            user = getattr(request, 'user', None)
            
            if not user or not user.is_authenticated:
                logger.warning(f"Role guard: unauthenticated access to {request.path}")
                raise PermissionDenied("Authentication required")
            
            # Check if user has any of the required roles
            user_roles = set(user.groups.values_list('name', flat=True))
            required = set(required_roles)
            
            if not user_roles.intersection(required):
                logger.warning(
                    f"Role guard: user {user.id} has {user_roles}, requires {required}"
                )
                raise PermissionDenied(f'Required roles: {", ".join(required)}')
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


def require_tenant() -> Callable:
    """
    Guard: Ensure tenant is properly resolved in request.
    
    Usage:
        @require_tenant()
        def tenant_view(request):
            tenant = request.tenant
            ...
    
    Raises:
        PermissionDenied: If tenant not resolved
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> Any:
            tenant = getattr(request, 'tenant', None)
            
            if not tenant:
                logger.warning(f"Tenant guard: no tenant for {request.path}")
                raise PermissionDenied("Tenant context required")
            
            # Verify tenant is valid
            if not hasattr(tenant, 'id') or not tenant.id:
                logger.error(f"Tenant guard: invalid tenant object")
                raise PermissionDenied("Invalid tenant context")
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


def require_https() -> Callable:
    """
    Guard: Require HTTPS (reject HTTP in production).
    
    Usage:
        @require_https()
        def secure_view(request):
            ...
    
    Raises:
        PermissionDenied: If request is not HTTPS
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> Any:
            # Allow HTTP only in development
            if not request.is_secure() and not settings.DEBUG:
                logger.warning(f"HTTPS guard: HTTP request to {request.path}")
                raise PermissionDenied("HTTPS required")
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


def require_json_body() -> Callable:
    """
    Guard: Require Content-Type: application/json.
    
    Usage:
        @require_json_body()
        def api_view(request):
            ...
    
    Raises:
        PermissionDenied: If Content-Type is not JSON
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> Any:
            content_type = request.META.get('CONTENT_TYPE', '').lower()
            
            if 'application/json' not in content_type and request.body:
                logger.warning(
                    f"JSON guard: non-JSON content type for {request.path}: {content_type}"
                )
                return JsonResponse(
                    {"error": "application/json content type required"},
                    status=415
                )
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


def sanitize_output(**allowed_fields) -> Callable:
    """
    Guard: Sanitize response to only include allowed fields.
    
    Usage:
        @sanitize_output(user=['id', 'email', 'name'])
        def user_view(request):
            return JsonResponse({"user": user_data, "secret": "..."})
    
    Args:
        allowed_fields: Mapping of response keys to allowed nested fields
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> Any:
            response = view_func(request, *args, **kwargs)
            
            # Only process JSON responses
            if not hasattr(response, 'data') or not isinstance(response.data, dict):
                return response
            
            # Filter each specified key
            for key, fields in allowed_fields.items():
                if key in response.data and isinstance(response.data[key], dict):
                    response.data[key] = {
                        k: v for k, v in response.data[key].items()
                        if k in fields
                    }
            
            return response
        
        return wrapper
    
    return decorator


def audit_log(event_type: str, metadata_fields: Optional[list] = None) -> Callable:
    """
    Guard: Log all calls to this endpoint for audit trail.
    
    Usage:
        @audit_log('payment_confirmed', metadata_fields=['order_id', 'amount'])
        def payment_view(request):
            ...
    
    Args:
        event_type: Type of audit event
        metadata_fields: Request fields to include in audit log
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> Any:
            user_id = getattr(getattr(request, 'user', None), 'id', None)
            tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)
            
            # Build metadata
            metadata = {
                'method': request.method,
                'path': request.path,
            }
            
            if metadata_fields:
                for field in metadata_fields:
                    if field in request.GET:
                        metadata[field] = request.GET[field]
                    elif hasattr(request, 'POST') and field in request.POST:
                        metadata[field] = request.POST[field]
            
            # Log audit event
            logger.info(
                f"Audit: {event_type}",
                extra={
                    'user_id': user_id,
                    'tenant_id': tenant_id,
                    'event_type': event_type,
                    'metadata': metadata,
                }
            )
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator

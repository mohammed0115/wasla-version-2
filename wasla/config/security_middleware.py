"""
Production-hardening security middleware for JWT tenant validation.

Enforces:
1. JWT tenant_id claim matches resolved tenant
2. Rejects mismatches with 403
3. Validates token signature before claim extraction
4. Logs all tenant resolution for audit trail
"""

import jwt
import logging
from typing import Optional
from django.http import JsonResponse
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from tenants.models import Tenant

logger = logging.getLogger("wasla.security")


class JWTTenantValidationMiddleware(MiddlewareMixin):
    """
    Validate JWT tenant_id claim matches resolved tenant.
    
    BEFORE processing request:
    1. Extract token from Authorization header
    2. Decode token (verify signature)
    3. Extract tenant_id from claims
    4. Compare against resolved tenant (from subdomain/custom domain)
    5. Reject if mismatch
    
    Flow:
    Authorization: Bearer <JWT>
    ↓
    Extract token
    ↓
    Verify signature (if tampered → invalid_signature error)
    ↓
    Extract claims (tenant_id, user_id, ...)
    ↓
    Resolve tenant from request (subdomain/custom domain)
    ↓
    Compare JWT tenant_id vs resolved tenant
    ↓
    If mismatch → 403 Forbidden (potential privilege escalation)
    If match → continue
    
    Security Guarantees:
    - Prevents JWT tampering (signature verification)
    - Prevents cross-tenant access (claim validation)
    - Prevents subdomain spoofing (double validation)
    - Audit logs all validation failures
    """
    
    EXCLUDED_PATHS = {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/health",
        "/metrics",
    }
    
    def should_validate(self, request) -> bool:
        """Skip validation for public endpoints."""
        path = request.path
        return not any(path.startswith(excluded) for excluded in self.EXCLUDED_PATHS)
    
    def process_request(self, request):
        """Validate JWT tenant claim before processing."""
        
        # Skip validation for excluded paths
        if not self.should_validate(request):
            return None
        
        # Skip if no Authorization header
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            # Will be caught by JWT auth view
            return None
        
        try:
            token = auth_header.split(" ")[1]
            
            # Decode token with signature verification
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"],
            )
            
            # Extract claims
            jwt_tenant_id = payload.get("tenant_id")
            jwt_user_id = payload.get("user_id")
            
            if not jwt_tenant_id:
                logger.warning(
                    "JWT validation failed: Missing tenant_id claim",
                    extra={
                        "user_id": jwt_user_id,
                        "path": request.path,
                        "method": request.method,
                    }
                )
                return JsonResponse(
                    {"error": "Invalid token: missing tenant_id claim"},
                    status=403
                )
            
            # Resolve tenant from request (already done by TenantMiddleware)
            resolved_tenant = getattr(request, "tenant", None)
            
            if not resolved_tenant:
                logger.warning(
                    "JWT validation failed: Could not resolve tenant from request",
                    extra={
                        "jwt_tenant_id": jwt_tenant_id,
                        "path": request.path,
                        "host": request.get_host(),
                    }
                )
                return JsonResponse(
                    {"error": "Could not resolve tenant"},
                    status=403
                )
            
            # CRITICAL: Compare JWT tenant_id with resolved tenant
            if str(jwt_tenant_id) != str(resolved_tenant.id):
                logger.warning(
                    "JWT tenant claim mismatch - POTENTIAL PRIVILEGE ESCALATION ATTEMPT",
                    extra={
                        "jwt_tenant_id": jwt_tenant_id,
                        "resolved_tenant_id": resolved_tenant.id,
                        "user_id": jwt_user_id,
                        "path": request.path,
                        "method": request.method,
                        "ip": self.get_client_ip(request),
                    }
                )
                return JsonResponse(
                    {"error": "Tenant claim mismatch"},
                    status=403
                )
            
            # Store decoded payload for later use
            request.jwt_payload = payload
            
            logger.debug(
                "JWT tenant validation passed",
                extra={
                    "tenant_id": jwt_tenant_id,
                    "user_id": jwt_user_id,
                    "path": request.path,
                }
            )
            
            return None
        
        except jwt.InvalidSignatureError:
            logger.warning(
                "JWT validation failed: Invalid signature (token tampered)",
                extra={
                    "path": request.path,
                    "ip": self.get_client_ip(request),
                }
            )
            return JsonResponse(
                {"error": "Invalid token signature"},
                status=403
            )
        
        except jwt.ExpiredSignatureError:
            # Let JWT auth views handle this
            return None
        
        except jwt.InvalidTokenError as e:
            logger.warning(
                f"JWT validation failed: {str(e)}",
                extra={
                    "path": request.path,
                    "ip": self.get_client_ip(request),
                }
            )
            return JsonResponse(
                {"error": "Invalid token"},
                status=403
            )
        
        except Exception as e:
            logger.error(
                f"Unexpected error in JWT validation: {str(e)}",
                extra={
                    "path": request.path,
                    "ip": self.get_client_ip(request),
                }
            )
            return JsonResponse(
                {"error": "Security validation error"},
                status=500
            )
    
    @staticmethod
    def get_client_ip(request) -> str:
        """Extract client IP from request (handles proxies)."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")


class TOTPVerificationMiddleware(MiddlewareMixin):
    """
    Enforce TOTP verification on sensitive merchant actions.
    
    Sensitive paths requiring 2FA:
    - /api/v1/merchant/settings (change settings)
    - /api/v1/merchant/payouts (request payout)
    - /api/v1/merchant/store (add store)
    - /api/v1/settlement/approve (admin: approve settlement)
    - /api/v1/refund (issue refund)
    - /api/v1/admin/user/create (admin: create user)
    
    Flow:
    POST /api/v1/merchant/payouts
    ↓ Check if merchant has 2FA enabled
    ↓ If yes: require X-TOTP-Code header
    ↓ Verify code matches current TOTP
    ↓ If valid: proceed, if invalid: 403
    """
    
    SENSITIVE_PATHS = {
        # Merchant operations
        "/api/v1/merchant/settings",
        "/api/v1/merchant/payouts",
        "/api/v1/merchant/store",
        "/api/v1/settlement/approve",
        "/api/v1/refund",
        
        # Admin operations
        "/api/v1/admin/user/create",
        "/api/v1/admin/user/update",
        "/api/v1/admin/settlement/approve",
    }
    
    def process_request(self, request):
        """Check if path requires TOTP verification."""
        
        # Only check POST/PUT/DELETE on sensitive paths
        if request.method not in ("POST", "PUT", "DELETE"):
            return None
        
        if not any(request.path.startswith(p) for p in self.SENSITIVE_PATHS):
            return None
        
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        
        # Check if user has 2FA enabled
        try:
            from accounts.models import TOTPSecret
            totp_secret = TOTPSecret.objects.filter(user=user, is_active=True).first()
        except Exception:
            return None
        
        if not totp_secret:
            # 2FA not enabled, allow
            return None
        
        # 2FA enabled: require X-TOTP-Code header
        totp_code = request.META.get("HTTP_X_TOTP_CODE", "")
        
        if not totp_code:
            logger.warning(
                "Sensitive operation attempted without TOTP code",
                extra={
                    "user_id": user.id,
                    "path": request.path,
                    "method": request.method,
                    "ip": JWTTenantValidationMiddleware.get_client_ip(request),
                }
            )
            return JsonResponse(
                {"error": "2FA required: X-TOTP-Code header missing"},
                status=403
            )
        
        # Verify TOTP code
        if not totp_secret.verify_token(totp_code):
            logger.warning(
                "Invalid TOTP code for sensitive operation",
                extra={
                    "user_id": user.id,
                    "path": request.path,
                    "method": request.method,
                    "ip": JWTTenantValidationMiddleware.get_client_ip(request),
                }
            )
            return JsonResponse(
                {"error": "Invalid TOTP code"},
                status=403
            )
        
        # Mark TOTP as verified for this request
        request.totp_verified = True
        logger.debug(
            "TOTP verification passed for sensitive operation",
            extra={
                "user_id": user.id,
                "path": request.path,
            }
        )
        
        return None

from __future__ import annotations

from functools import wraps
from typing import Callable

from django.conf import settings
from django.core.exceptions import PermissionDenied

from apps.tenants.models import Permission, RolePermission, TenantMembership
from apps.tenants.models import Tenant
from core.infrastructure.store_cache import StoreCacheService


_REQUEST_PERMISSION_CODES_ATTR = "_rbac_permission_codes"
_REQUEST_MEMBERSHIP_ATTR = "_rbac_membership"


def _resolve_request_object(args: tuple, kwargs: dict):
    if "request" in kwargs:
        return kwargs["request"]
    for arg in args:
        if hasattr(arg, "META") and hasattr(arg, "user"):
            return arg
    if len(args) >= 2 and hasattr(args[1], "META") and hasattr(args[1], "user"):
        return args[1]
    return None


def _resolve_tenant_from_request(request):
    tenant = getattr(request, "tenant", None)
    if tenant is not None:
        return tenant
    store = getattr(request, "store", None)
    if store is not None:
        return getattr(store, "tenant", None)

    session = getattr(request, "session", None)
    raw_store_id = None
    if session is not None:
        raw_store_id = session.get("store_id")
    try:
        store_id = int(raw_store_id) if raw_store_id is not None else None
    except (TypeError, ValueError):
        store_id = None
    if store_id:
        return Tenant.objects.filter(id=store_id, is_active=True).first()

    return None


def resolve_membership(request):
    cached_membership = getattr(request, _REQUEST_MEMBERSHIP_ATTR, None)
    if cached_membership is not None:
        return cached_membership

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        setattr(request, _REQUEST_MEMBERSHIP_ATTR, None)
        return None

    tenant = _resolve_tenant_from_request(request)
    if tenant is None:
        setattr(request, _REQUEST_MEMBERSHIP_ATTR, None)
        return None

    membership = (
        TenantMembership.objects.filter(
            tenant_id=tenant.id,
            user_id=user.id,
            is_active=True,
        )
        .only("id", "tenant_id", "user_id", "role", "is_active")
        .first()
    )
    setattr(request, _REQUEST_MEMBERSHIP_ATTR, membership)
    return membership


def resolve_permissions_for_request(request) -> set[str]:
    cached_permissions = getattr(request, _REQUEST_PERMISSION_CODES_ATTR, None)
    if cached_permissions is not None:
        return cached_permissions

    user = getattr(request, "user", None)
    if user and getattr(user, "is_superuser", False):
        all_codes = set(Permission.objects.values_list("code", flat=True))
        setattr(request, _REQUEST_PERMISSION_CODES_ATTR, all_codes)
        return all_codes

    membership = resolve_membership(request)
    if membership is None:
        setattr(request, _REQUEST_PERMISSION_CODES_ATTR, set())
        return set()

    store_id = int(getattr(membership, "tenant_id", 0) or 0)
    ttl = int(getattr(settings, "CACHE_TTL_SHORT", 60) or 60)

    if membership.role == TenantMembership.ROLE_OWNER:
        def _all_codes():
            return set(Permission.objects.values_list("code", flat=True))

        all_codes, _ = StoreCacheService.get_or_set(
            store_id=store_id,
            namespace="rbac_permissions",
            key_parts=["owner", membership.user_id],
            producer=_all_codes,
            timeout=ttl,
        )
        setattr(request, _REQUEST_PERMISSION_CODES_ATTR, all_codes)
        return all_codes

    def _role_permissions():
        return set(RolePermission.objects.filter(role=membership.role).values_list("permission__code", flat=True))

    permission_codes, _ = StoreCacheService.get_or_set(
        store_id=store_id,
        namespace="rbac_permissions",
        key_parts=["member", membership.user_id, membership.role],
        producer=_role_permissions,
        timeout=ttl,
    )
    setattr(request, _REQUEST_PERMISSION_CODES_ATTR, permission_codes)
    return permission_codes


def has_permission(request, permission_code: str) -> bool:
    permission_codes = resolve_permissions_for_request(request)
    return permission_code in permission_codes


def require_permission(*args) -> Callable | bool:
    """
    Dual-use permission gate:
    - As decorator: @require_permission("perm.code")
    - As inline check: require_permission(request, "perm.code")
    """
    if len(args) == 1 and isinstance(args[0], str):
        permission_code = args[0]

        def decorator(view_func: Callable) -> Callable:
            @wraps(view_func)
            def _wrapped(*view_args, **view_kwargs):
                request = _resolve_request_object(view_args, view_kwargs)
                if request is None:
                    raise PermissionDenied("Invalid request context")
                if not has_permission(request, permission_code):
                    raise PermissionDenied(f"Missing permission: {permission_code}")
                return view_func(*view_args, **view_kwargs)

            return _wrapped

        return decorator

    if len(args) == 2:
        request, permission_code = args
        if not isinstance(permission_code, str):
            raise TypeError("permission_code must be a string")
        if not has_permission(request, permission_code):
            raise PermissionDenied(f"Missing permission: {permission_code}")
        return True

    raise TypeError("require_permission expects (permission_code) or (request, permission_code)")

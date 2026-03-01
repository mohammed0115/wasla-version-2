from __future__ import annotations

from functools import wraps
from typing import Iterable

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .models import AdminRole, AdminUserRole


SUPERADMIN_ROLE_NAME = "SUPERADMIN"
PORTAL_ACCESS_PERMISSION = "portal.access"


def _ensure_superuser_role(user) -> AdminUserRole | None:
    if not getattr(user, "is_superuser", False):
        return None

    role, _ = AdminRole.objects.get_or_create(
        name=SUPERADMIN_ROLE_NAME,
        defaults={"description": "Full access"},
    )
    user_role, created = AdminUserRole.objects.get_or_create(user=user, defaults={"role": role})
    if not created and user_role.role_id != role.id:
        user_role.role = role
        user_role.save(update_fields=["role"])
    return user_role


def _get_user_role(user) -> AdminRole | None:
    try:
        return user.admin_user_role.role
    except (AdminUserRole.DoesNotExist, AttributeError):
        return None


def admin_has_permission(user, permission_code: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False):
        _ensure_superuser_role(user)
        return True

    role = _get_user_role(user)
    if role is None:
        return False

    if role.name == SUPERADMIN_ROLE_NAME:
        return True

    return role.role_permissions.filter(permission__code=permission_code).exists()


def admin_portal_required(view_func):
    """Require portal access permission for admin portal access."""
    return admin_permission_required(PORTAL_ACCESS_PERMISSION)(view_func)


def admin_permission_required(permission_codes: Iterable[str] | str, require_all: bool = False):
    if isinstance(permission_codes, str):
        normalized_codes = [permission_codes]
    else:
        normalized_codes = list(permission_codes)

    additional_codes = [code for code in normalized_codes if code != PORTAL_ACCESS_PERMISSION]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), login_url='/admin-portal/login/')

            if request.user.is_superuser:
                _ensure_superuser_role(request.user)
                return view_func(request, *args, **kwargs)

            role = _get_user_role(request.user)
            if role is None:
                raise PermissionDenied("Admin role assignment is required")

            if role.name == SUPERADMIN_ROLE_NAME:
                return view_func(request, *args, **kwargs)

            if not admin_has_permission(request.user, PORTAL_ACCESS_PERMISSION):
                raise PermissionDenied("Admin portal access is required")

            if additional_codes:
                checks = [admin_has_permission(request.user, code) for code in additional_codes]
                allowed = all(checks) if require_all else any(checks)
                if not allowed:
                    raise PermissionDenied("Insufficient admin permissions")

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator

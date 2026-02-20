from functools import wraps
from django.core.exceptions import PermissionDenied

from .models import AdminUserRole


def admin_portal_required(view_func):
    """Require staff status for admin portal access."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path(), login_url='/admin-portal/login/')
        
        if not request.user.is_staff:
            raise PermissionDenied("Staff access required")
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view


def _get_user_role(user):
    try:
        return user.admin_user_role.role
    except AdminUserRole.DoesNotExist:
        return None


def admin_has_permission(user, permission_code: str) -> bool:
    if not user.is_authenticated or not user.is_staff:
        return False

    role = _get_user_role(user)
    if role is None:
        return False

    if role.name == "SuperAdmin":
        return True

    return role.role_permissions.filter(permission__code=permission_code).exists()


def admin_permission_required(permission_codes, require_all: bool = False):
    if isinstance(permission_codes, str):
        normalized_codes = [permission_codes]
    else:
        normalized_codes = list(permission_codes)

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path(), login_url='/admin-portal/login/')

            if not request.user.is_staff:
                raise PermissionDenied("Staff access required")

            role = _get_user_role(request.user)
            if role is None:
                raise PermissionDenied("Admin role assignment is required")

            if role.name == "SuperAdmin":
                return view_func(request, *args, **kwargs)

            checks = [admin_has_permission(request.user, code) for code in normalized_codes]
            allowed = all(checks) if require_all else any(checks)
            if not allowed:
                raise PermissionDenied("Insufficient admin permissions")

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator

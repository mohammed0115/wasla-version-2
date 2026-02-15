from __future__ import annotations

from rest_framework.permissions import BasePermission

from tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from tenants.domain.errors import StoreAccessDeniedError, StoreInactiveError
from tenants.models import Tenant


class HasTenantAccess(BasePermission):
    message = "Tenant access required."

    def has_permission(self, request, view) -> bool:
        tenant = getattr(request, "tenant", None)
        if not isinstance(tenant, Tenant):
            return False

        try:
            EnsureTenantOwnershipPolicy.ensure_can_access(user=request.user, tenant=tenant)
        except (StoreAccessDeniedError, StoreInactiveError):
            return False

        raw_store_id = getattr(view, "kwargs", {}).get("store_id")
        if raw_store_id is None:
            return True

        try:
            store_id = int(raw_store_id)
        except (TypeError, ValueError):
            return False

        return store_id == tenant.id


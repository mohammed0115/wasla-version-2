from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

from tenants.domain.errors import StoreAccessDeniedError, StoreInactiveError
from tenants.models import Tenant, TenantMembership


class EnsureTenantOwnershipPolicy:
    @staticmethod
    def _is_superuser(user: AbstractBaseUser | AnonymousUser) -> bool:
        return bool(getattr(user, "is_authenticated", False) and getattr(user, "is_superuser", False))

    @staticmethod
    def ensure_can_access(*, user: AbstractBaseUser | AnonymousUser, tenant: Tenant) -> None:
        if not tenant.is_active:
            raise StoreInactiveError("Store is inactive.")
        if EnsureTenantOwnershipPolicy._is_superuser(user):
            return
        if not getattr(user, "is_authenticated", False):
            raise StoreAccessDeniedError("Authentication required.")

        profile_owner_id = None
        if hasattr(tenant, "store_profile"):
            profile_owner_id = getattr(tenant.store_profile, "owner_id", None)
        if profile_owner_id and getattr(user, "id", None) == profile_owner_id:
            return

        ok = TenantMembership.objects.filter(
            tenant=tenant,
            user=user,
            is_active=True,
        ).exists()
        if not ok:
            raise StoreAccessDeniedError("You do not have access to this store.")

    @staticmethod
    def ensure_is_owner(*, user: AbstractBaseUser | AnonymousUser, tenant: Tenant) -> None:
        if EnsureTenantOwnershipPolicy._is_superuser(user):
            return
        if not getattr(user, "is_authenticated", False):
            raise StoreAccessDeniedError("Authentication required.")

        profile_owner_id = None
        if hasattr(tenant, "store_profile"):
            profile_owner_id = getattr(tenant.store_profile, "owner_id", None)
        if profile_owner_id and getattr(user, "id", None) == profile_owner_id:
            return

        ok = TenantMembership.objects.filter(
            tenant=tenant,
            user=user,
            role=TenantMembership.ROLE_OWNER,
            is_active=True,
        ).exists()
        if not ok:
            raise StoreAccessDeniedError("Only the store owner can perform this action.")

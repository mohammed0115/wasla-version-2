from __future__ import annotations

from typing import Optional

from django.conf import settings
from rest_framework.permissions import BasePermission

from apps.tenants.models import Tenant, TenantMembership
from apps.stores.models import Store


class TenantTokenAuth(BasePermission):
    """
    DRF permission that enforces tenant resolution + membership access.

    Resolution order:
    1) request.tenant (set by middleware)
    2) X-Tenant / X-Tenant-Id header (id or slug)
    """

    message = "Tenant access denied."

    def get_tenant_id(self, request) -> Optional[int]:
        tenant = getattr(request, "tenant", None)
        if tenant:
            return tenant.id

        raw_header = (
            request.headers.get("X-Tenant")
            or request.headers.get("X-Tenant-Id")
            or request.headers.get("X-Tenant-ID")
        )
        if not raw_header:
            return None

        raw_header = raw_header.strip()
        tenant_obj = None
        try:
            header_store_id = int(raw_header)
        except (TypeError, ValueError):
            header_store_id = None

        if header_store_id is not None:
            tenant_obj = Tenant.objects.filter(id=header_store_id, is_active=True).first()
        else:
            tenant_obj = Tenant.objects.filter(slug=raw_header, is_active=True).first()

        if tenant_obj:
            request.tenant = tenant_obj
            self._attach_store(request, tenant_obj)
            return tenant_obj.id
        return None

    def has_permission(self, request, view) -> bool:
        tenant_id = self.get_tenant_id(request)
        if tenant_id is None:
            return False

        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            # Let other permissions enforce auth when required.
            return True

        if getattr(user, "is_superuser", False) and getattr(settings, "TENANT_BYPASS_SUPERADMIN", True):
            return True

        has_membership = TenantMembership.objects.filter(
            tenant_id=tenant_id,
            user=user,
            is_active=True,
        ).exists()
        if has_membership:
            return True

        return Store.objects.filter(tenant_id=tenant_id, owner=user).exists()

    @staticmethod
    def _attach_store(request, tenant: Tenant) -> None:
        if getattr(request, "store", None):
            return
        store = Store.objects.filter(tenant_id=tenant.id).order_by("id").first()
        if store:
            request.store = store


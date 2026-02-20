from __future__ import annotations

from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.db import models


class TenantQuerySet(models.QuerySet):
    def for_tenant(self, tenant: Any):
        tenant_id = getattr(tenant, "id", tenant)
        store_id = getattr(tenant, "store_id", None)

        try:
            self.model._meta.get_field("store")
            if store_id is not None:
                return self.filter(store=store_id)
        except Exception:
            pass

        try:
            self.model._meta.get_field("store_id")
            return self.filter(store_id=store_id if store_id is not None else tenant_id)
        except Exception:
            pass

        tenant_field = getattr(self.model, "TENANT_FIELD", None)
        if tenant_field:
            return self.filter(**{tenant_field: tenant_id})

        try:
            self.model._meta.get_field("tenant")
            return self.filter(tenant=tenant_id)
        except Exception:
            pass

        raise ImproperlyConfigured(
            f"{self.model.__name__} must define TENANT_FIELD or a tenant/store_id field for tenant scoping."
        )


class TenantManager(models.Manager):
    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db)

    def for_tenant(self, tenant: Any):
        return self.get_queryset().for_tenant(tenant)


def get_object_for_tenant(model, tenant, **lookup):
    return model.objects.for_tenant(tenant).get(**lookup)

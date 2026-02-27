from __future__ import annotations

from typing import Any, Iterator
import contextvars
from contextlib import contextmanager

from django.core.exceptions import ImproperlyConfigured
from django.db import models


_tenant_context: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "tenant_context",
    default={"tenant_id": None, "store_id": None, "bypass": False},
)


def get_current_tenant_context() -> dict:
    return _tenant_context.get()


def set_current_tenant_context(*, tenant_id: int | None, store_id: int | None, bypass: bool = False):
    return _tenant_context.set({"tenant_id": tenant_id, "store_id": store_id, "bypass": bool(bypass)})


def reset_current_tenant_context(token) -> None:
    _tenant_context.reset(token)


@contextmanager
def tenant_bypass() -> Iterator[None]:
    ctx = get_current_tenant_context()
    token = _tenant_context.set({**ctx, "bypass": True})
    try:
        yield
    finally:
        _tenant_context.reset(token)


def _model_is_tenant_scoped(model: type[models.Model]) -> bool:
    try:
        model._meta.get_field("store")
        return True
    except Exception:
        pass

    try:
        model._meta.get_field("store_id")
        return True
    except Exception:
        pass

    tenant_field = getattr(model, "TENANT_FIELD", None)
    if tenant_field:
        return True

    try:
        model._meta.get_field("tenant")
        return True
    except Exception:
        pass

    try:
        model._meta.get_field("tenant_id")
        return True
    except Exception:
        pass

    return False


def _build_tenant_filter(model: type[models.Model], *, tenant_id: int | None, store_id: int | None) -> dict:
    resolved_store_id = store_id if store_id is not None else tenant_id
    if resolved_store_id is None and tenant_id is None:
        return {}

    try:
        model._meta.get_field("store")
        if resolved_store_id is None:
            return {}
        return {"store_id": resolved_store_id}
    except Exception:
        pass

    try:
        model._meta.get_field("store_id")
        if resolved_store_id is None:
            return {}
        return {"store_id": resolved_store_id}
    except Exception:
        pass

    tenant_field = getattr(model, "TENANT_FIELD", None)
    if tenant_field:
        if tenant_id is None:
            return {}
        return {tenant_field: tenant_id}

    try:
        model._meta.get_field("tenant")
        if tenant_id is None:
            return {}
        return {"tenant_id": tenant_id}
    except Exception:
        pass

    try:
        model._meta.get_field("tenant_id")
        if tenant_id is None:
            return {}
        return {"tenant_id": tenant_id}
    except Exception:
        pass

    return {}


def _has_explicit_tenant_values(model: type[models.Model], kwargs: dict) -> bool:
    if "store" in kwargs or "store_id" in kwargs:
        return True
    if "tenant" in kwargs or "tenant_id" in kwargs:
        return True
    tenant_field = getattr(model, "TENANT_FIELD", None)
    if tenant_field and tenant_field in kwargs:
        return True
    return False


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

    def _apply_context_scope(self):
        ctx = get_current_tenant_context()
        if ctx.get("bypass"):
            return self
        if not _model_is_tenant_scoped(self.model):
            return self

        tenant_id = ctx.get("tenant_id")
        store_id = ctx.get("store_id")
        if tenant_id is None and store_id is None:
            raise ImproperlyConfigured(
                f"Tenant context is required to query {self.model.__name__}. "
                "Use tenant_bypass() for superadmin operations."
            )

        filters = _build_tenant_filter(self.model, tenant_id=tenant_id, store_id=store_id)
        if not filters:
            raise ImproperlyConfigured(
                f"{self.model.__name__} must define TENANT_FIELD or a tenant/store_id field for tenant scoping."
            )
        return self.filter(**filters)


class TenantManager(models.Manager):
    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db)._apply_context_scope()

    def for_tenant(self, tenant: Any):
        return self.get_queryset().for_tenant(tenant)

    def create(self, **kwargs):
        ctx = get_current_tenant_context()
        if not ctx.get("bypass") and _model_is_tenant_scoped(self.model):
            if ctx.get("tenant_id") is None and ctx.get("store_id") is None:
                if not _has_explicit_tenant_values(self.model, kwargs):
                    raise ValueError(
                        f"{self.model.__name__} create requires tenant/store fields or tenant context."
                    )
        return TenantQuerySet(self.model, using=self._db).create(**kwargs)

    def bulk_create(self, objs, **kwargs):
        ctx = get_current_tenant_context()
        if not ctx.get("bypass") and _model_is_tenant_scoped(self.model):
            if ctx.get("tenant_id") is None and ctx.get("store_id") is None:
                for obj in objs:
                    tenant_id, store_id = getattr(obj, "tenant_id", None), getattr(obj, "store_id", None)
                    if tenant_id is None and store_id is None:
                        raise ValueError(
                            f"{self.model.__name__} bulk_create requires tenant/store fields or tenant context."
                        )
        return TenantQuerySet(self.model, using=self._db).bulk_create(objs, **kwargs)


def get_object_for_tenant(model, tenant, **lookup):
    return model.objects.for_tenant(tenant).get(**lookup)

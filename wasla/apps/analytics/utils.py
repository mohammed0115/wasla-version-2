from __future__ import annotations

from typing import Any

from apps.stores.models import Store


def resolve_store_id(request: Any) -> int | None:
    """
    Resolve the current store ID from request context.

    Priority:
    1) request.store
    2) request.tenant -> first store for tenant
    3) session store_id (tenant id or store id)
    4) first store owned by user
    """
    store = getattr(request, "store", None)
    if store and getattr(store, "id", None):
        return store.id

    tenant = getattr(request, "tenant", None)
    if tenant:
        store = Store.objects.filter(tenant=tenant).order_by("id").first()
        if store:
            request.store = store
            return store.id

    store_id = None
    if hasattr(request, "session"):
        raw_store_id = request.session.get("store_id")
        try:
            store_id = int(raw_store_id) if raw_store_id is not None else None
        except (TypeError, ValueError):
            store_id = None

    if store_id:
        store = Store.objects.filter(id=store_id).order_by("id").first()
        if store:
            request.store = store
            request.tenant = store.tenant
            return store.id
        store = Store.objects.filter(tenant_id=store_id).order_by("id").first()
        if store:
            request.store = store
            request.tenant = store.tenant
            return store.id

    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        store = Store.objects.filter(owner=user).order_by("id").first()
        if store:
            request.store = store
            request.tenant = store.tenant
            return store.id

    return None

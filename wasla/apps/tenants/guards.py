from __future__ import annotations

from django.http import Http404
from django.core.exceptions import ImproperlyConfigured, PermissionDenied

from .managers import get_object_for_tenant


def require_store(request):
    store = getattr(request, "store", None)
    if not store:
        raise Http404("Store not found.")
    return store


def require_tenant(request):
    tenant = getattr(request, "tenant", None)
    if tenant:
        return tenant

    store = getattr(request, "store", None)
    if store and getattr(store, "tenant", None):
        request.tenant = store.tenant
        return store.tenant

    raise Http404("Tenant not found.")


def require_merchant(request):
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentication required.")

    store = getattr(request, "store", None)
    tenant = None
    if store and getattr(store, "tenant", None):
        tenant = store.tenant
    else:
        tenant = getattr(request, "tenant", None)

    if not tenant:
        raise PermissionDenied("Tenant not found.")

    if store and getattr(store, "tenant_id", None) and getattr(tenant, "id", None):
        if store.tenant_id != tenant.id:
            raise PermissionDenied("Tenant mismatch.")

    if getattr(user, "is_superuser", False):
        return tenant

    profile_owner_id = None
    try:
        profile_owner_id = getattr(tenant.store_profile, "owner_id", None)
    except Exception:
        profile_owner_id = None
    if profile_owner_id and getattr(user, "id", None) == profile_owner_id:
        return tenant

    from .models import TenantMembership

    if TenantMembership.objects.filter(tenant=tenant, user=user, is_active=True).exists():
        return tenant

    user_tenant = getattr(user, "tenant", None)
    if user_tenant and getattr(user_tenant, "id", None) == tenant.id:
        return tenant

    raise PermissionDenied("You do not have access to this store.")


def tenant_object_or_404(model, tenant, **lookup):
    try:
        return get_object_for_tenant(model, tenant, **lookup)
    except model.DoesNotExist as exc:
        raise Http404("Not found.") from exc


def store_object_or_404(model, store, **lookup):
    store_id = getattr(store, "id", store)
    try:
        model._meta.get_field("store")
        scoped_lookup = {"store": store_id}
    except Exception:
        try:
            model._meta.get_field("store_id")
            scoped_lookup = {"store_id": store_id}
        except Exception as exc:
            raise ImproperlyConfigured(
                f"{model.__name__} must define a store/store_id field for store scoping."
            ) from exc

    try:
        return model.objects.get(**{**scoped_lookup, **lookup})
    except model.DoesNotExist as exc:
        raise Http404("Not found.") from exc

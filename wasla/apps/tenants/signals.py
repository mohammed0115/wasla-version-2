from __future__ import annotations

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.apps import apps

from apps.tenants.models import Tenant
from apps.tenants.services.audit_service import TenantAuditService
from apps.tenants.managers import get_current_tenant_context, _model_is_tenant_scoped


@receiver(pre_save, sender=Tenant)
def _tenant_pre_save(sender, instance: Tenant, **kwargs):
    if instance.pk:
        instance._pre_save_is_active = (
            Tenant.objects.filter(pk=instance.pk).values_list("is_active", flat=True).first()
        )
    else:
        instance._pre_save_is_active = None


@receiver(post_save, sender=Tenant)
def _tenant_post_save(sender, instance: Tenant, created: bool, **kwargs):
    if created:
        TenantAuditService.record_action(instance, "tenant_created")
        return

    was_active = getattr(instance, "_pre_save_is_active", None)
    if was_active is True and instance.is_active is False:
        TenantAuditService.record_action(instance, "tenant_deactivated")


def _extract_instance_scope(instance):
    store_id = getattr(instance, "store_id", None)
    if store_id is None and getattr(instance, "store", None) is not None:
        store_id = getattr(instance.store, "id", None)
    tenant_id = getattr(instance, "tenant_id", None)
    if tenant_id is None and getattr(instance, "tenant", None) is not None:
        tenant_id = getattr(instance.tenant, "id", None)
    tenant_field = getattr(instance, "TENANT_FIELD", None)
    if tenant_field:
        tenant_id = getattr(instance, tenant_field, tenant_id)
    return tenant_id, store_id


def _tenant_guard_pre_save(sender, instance, **kwargs):
    ctx = get_current_tenant_context()
    if ctx.get("bypass"):
        return
    if not _model_is_tenant_scoped(sender):
        return

    ctx_tenant_id = ctx.get("tenant_id")
    ctx_store_id = ctx.get("store_id")
    if ctx_tenant_id is None and ctx_store_id is None:
        return

    tenant_id, store_id = _extract_instance_scope(instance)
    if tenant_id is None and store_id is None:
        raise ValueError(f"{sender.__name__} save blocked: tenant/store context required.")

    if ctx_store_id is not None and store_id is not None and int(store_id) != int(ctx_store_id):
        raise ValueError(f"{sender.__name__} save blocked: store mismatch.")

    if ctx_tenant_id is not None and tenant_id is not None and int(tenant_id) != int(ctx_tenant_id):
        raise ValueError(f"{sender.__name__} save blocked: tenant mismatch.")


def register_tenant_save_guards():
    for model in apps.get_models():
        if model._meta.abstract or model._meta.proxy:
            continue
        if not _model_is_tenant_scoped(model):
            continue
        pre_save.connect(
            _tenant_guard_pre_save,
            sender=model,
            weak=False,
            dispatch_uid=f"tenant_guard_pre_save:{model._meta.label_lower}",
        )

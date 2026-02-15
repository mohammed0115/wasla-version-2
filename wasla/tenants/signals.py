from __future__ import annotations

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from tenants.models import Tenant
from tenants.services.audit_service import TenantAuditService


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

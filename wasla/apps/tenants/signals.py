from __future__ import annotations

from django.conf import settings
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from apps.tenants.models import Tenant, StoreDomain
from apps.tenants.services.audit_service import TenantAuditService
from apps.tenants.services.domain_resolution import invalidate_domain_cache, invalidate_store_host_cache


@receiver(pre_save, sender=Tenant)
def _tenant_pre_save(sender, instance: Tenant, **kwargs):
    if instance.pk:
        previous = (
            Tenant.objects.filter(pk=instance.pk)
            .values_list("is_active", "domain", "subdomain", "slug")
            .first()
        )
        if previous:
            instance._pre_save_is_active = previous[0]
            instance._pre_save_domain = previous[1]
            instance._pre_save_subdomain = previous[2]
            instance._pre_save_slug = previous[3]
        else:
            instance._pre_save_is_active = None
            instance._pre_save_domain = None
            instance._pre_save_subdomain = None
            instance._pre_save_slug = None
    else:
        instance._pre_save_is_active = None
        instance._pre_save_domain = None
        instance._pre_save_subdomain = None
        instance._pre_save_slug = None


@receiver(post_save, sender=Tenant)
def _tenant_post_save(sender, instance: Tenant, created: bool, **kwargs):
    if created:
        TenantAuditService.record_action(instance, "tenant_created")
        return

    was_active = getattr(instance, "_pre_save_is_active", None)
    if was_active is True and instance.is_active is False:
        TenantAuditService.record_action(instance, "tenant_deactivated")

    _invalidate_tenant_domain_cache(instance)


@receiver(pre_save, sender=StoreDomain)
def _storedomain_pre_save(sender, instance: StoreDomain, **kwargs):
    if instance.pk:
        instance._pre_save_domain = (
            StoreDomain.objects.filter(pk=instance.pk).values_list("domain", flat=True).first()
        )
    else:
        instance._pre_save_domain = None


@receiver(post_save, sender=StoreDomain)
def _storedomain_post_save(sender, instance: StoreDomain, created: bool, **kwargs):
    old_domain = getattr(instance, "_pre_save_domain", None)
    if old_domain and old_domain != instance.domain:
        invalidate_domain_cache(old_domain)
        invalidate_store_host_cache(old_domain)
    if instance.domain:
        invalidate_domain_cache(instance.domain)
        invalidate_store_host_cache(instance.domain)


@receiver(post_delete, sender=StoreDomain)
def _storedomain_post_delete(sender, instance: StoreDomain, **kwargs):
    if instance.domain:
        invalidate_domain_cache(instance.domain)
        invalidate_store_host_cache(instance.domain)


def _invalidate_tenant_domain_cache(instance: Tenant) -> None:
    base_domain = (getattr(settings, "WASSLA_BASE_DOMAIN", "") or "").strip().lower()
    hosts: set[str] = set()

    for value in (
        getattr(instance, "_pre_save_domain", None),
        getattr(instance, "domain", None),
    ):
        if value:
            hosts.add(value)

    for label in (
        getattr(instance, "_pre_save_subdomain", None),
        getattr(instance, "_pre_save_slug", None),
        getattr(instance, "subdomain", None),
        getattr(instance, "slug", None),
    ):
        label_norm = (label or "").strip().lower()
        if label_norm and base_domain:
            hosts.add(f"{label_norm}.{base_domain}")

    for host in hosts:
        invalidate_domain_cache(host)

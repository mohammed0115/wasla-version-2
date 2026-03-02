from __future__ import annotations

from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from apps.stores.models import Store
from django.conf import settings

from apps.tenants.services.domain_resolution import (
    invalidate_store_host_cache,
    invalidate_store_slug_cache,
    invalidate_store_subdomain_cache,
)


@receiver(pre_save, sender=Store)
def _store_pre_save(sender, instance: Store, **kwargs):
    if instance.pk:
        previous = (
            Store.objects.filter(pk=instance.pk)
            .values_list("slug", "subdomain")
            .first()
        )
        instance._pre_save_slug = previous[0] if previous else None
        instance._pre_save_subdomain = previous[1] if previous else None
    else:
        instance._pre_save_slug = None
        instance._pre_save_subdomain = None


@receiver(post_save, sender=Store)
def _store_post_save(sender, instance: Store, created: bool, **kwargs):
    old_slug = getattr(instance, "_pre_save_slug", None)
    if old_slug and old_slug != instance.slug:
        invalidate_store_slug_cache(old_slug)
    if instance.slug:
        invalidate_store_slug_cache(instance.slug)

    old_subdomain = getattr(instance, "_pre_save_subdomain", None)
    base_domain = (getattr(settings, "WASSLA_BASE_DOMAIN", "") or "").strip().lower()
    if old_subdomain and old_subdomain != instance.subdomain:
        invalidate_store_subdomain_cache(old_subdomain)
        if base_domain:
            invalidate_store_host_cache(f"{old_subdomain}.{base_domain}")
    if instance.subdomain:
        invalidate_store_subdomain_cache(instance.subdomain)
        if base_domain:
            invalidate_store_host_cache(f"{instance.subdomain}.{base_domain}")


@receiver(post_delete, sender=Store)
def _store_post_delete(sender, instance: Store, **kwargs):
    if instance.slug:
        invalidate_store_slug_cache(instance.slug)
    if instance.subdomain:
        invalidate_store_subdomain_cache(instance.subdomain)
        base_domain = (getattr(settings, "WASSLA_BASE_DOMAIN", "") or "").strip().lower()
        if base_domain:
            invalidate_store_host_cache(f"{instance.subdomain}.{base_domain}")

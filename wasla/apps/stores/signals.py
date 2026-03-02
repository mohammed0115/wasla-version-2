from __future__ import annotations

from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from apps.stores.models import Store
from apps.tenants.services.domain_resolution import invalidate_store_slug_cache


@receiver(pre_save, sender=Store)
def _store_pre_save(sender, instance: Store, **kwargs):
    if instance.pk:
        instance._pre_save_slug = (
            Store.objects.filter(pk=instance.pk).values_list("slug", flat=True).first()
        )
    else:
        instance._pre_save_slug = None


@receiver(post_save, sender=Store)
def _store_post_save(sender, instance: Store, created: bool, **kwargs):
    old_slug = getattr(instance, "_pre_save_slug", None)
    if old_slug and old_slug != instance.slug:
        invalidate_store_slug_cache(old_slug)
    if instance.slug:
        invalidate_store_slug_cache(instance.slug)


@receiver(post_delete, sender=Store)
def _store_post_delete(sender, instance: Store, **kwargs):
    if instance.slug:
        invalidate_store_slug_cache(instance.slug)

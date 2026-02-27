from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.catalog.models import Category, Product, ProductVariant
from apps.stores.models import StoreSettings
from apps.subscriptions.models import StoreSubscription, SubscriptionPlan
from apps.tenants.models import Permission, RolePermission, StorePaymentSettings, StoreShippingSettings, Tenant
from apps.tenants.models import TenantMembership
from core.infrastructure.store_cache import StoreCacheService


def _bump_catalog_namespaces(store_id: int):
    StoreCacheService.bump_namespace_version(store_id=store_id, namespace="storefront_products")
    StoreCacheService.bump_namespace_version(store_id=store_id, namespace="product_detail")
    StoreCacheService.bump_namespace_version(store_id=store_id, namespace="variant_price")


def _bump_store_config_namespace(store_id: int):
    StoreCacheService.bump_namespace_version(store_id=store_id, namespace="store_config")


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
def invalidate_product_cache(sender, instance: Product, **kwargs):
    _bump_catalog_namespaces(store_id=int(instance.store_id))


@receiver(post_save, sender=ProductVariant)
@receiver(post_delete, sender=ProductVariant)
def invalidate_variant_cache(sender, instance: ProductVariant, **kwargs):
    _bump_catalog_namespaces(store_id=int(instance.store_id))


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
def invalidate_category_cache(sender, instance: Category, **kwargs):
    _bump_catalog_namespaces(store_id=int(instance.store_id))


@receiver(post_save, sender=StoreSettings)
@receiver(post_delete, sender=StoreSettings)
def invalidate_store_settings_cache(sender, instance: StoreSettings, **kwargs):
    _bump_catalog_namespaces(store_id=int(instance.store_id))
    _bump_store_config_namespace(store_id=int(instance.store_id))


@receiver(post_save, sender=StorePaymentSettings)
@receiver(post_delete, sender=StorePaymentSettings)
def invalidate_payment_settings_cache(sender, instance: StorePaymentSettings, **kwargs):
    _bump_catalog_namespaces(store_id=int(instance.tenant_id))
    _bump_store_config_namespace(store_id=int(instance.tenant_id))


@receiver(post_save, sender=StoreShippingSettings)
@receiver(post_delete, sender=StoreShippingSettings)
def invalidate_shipping_settings_cache(sender, instance: StoreShippingSettings, **kwargs):
    _bump_catalog_namespaces(store_id=int(instance.tenant_id))
    _bump_store_config_namespace(store_id=int(instance.tenant_id))


@receiver(post_save, sender=StoreSubscription)
@receiver(post_delete, sender=StoreSubscription)
def invalidate_subscription_cache(sender, instance: StoreSubscription, **kwargs):
    _bump_catalog_namespaces(store_id=int(instance.store_id))
    _bump_store_config_namespace(store_id=int(instance.store_id))
    _invalidate_rbac_for_store(int(instance.store_id))


@receiver(post_save, sender=Tenant)
@receiver(post_delete, sender=Tenant)
def invalidate_tenant_domain_and_theme_cache(sender, instance: Tenant, **kwargs):
    _bump_store_config_namespace(store_id=int(instance.id))


@receiver(post_save, sender=SubscriptionPlan)
@receiver(post_delete, sender=SubscriptionPlan)
def invalidate_plan_changes_permissions(sender, **kwargs):
    for store_id in StoreSubscription.objects.values_list("store_id", flat=True).distinct():
        _invalidate_rbac_for_store(int(store_id))


def _invalidate_rbac_for_store(store_id: int):
    StoreCacheService.bump_namespace_version(store_id=store_id, namespace="rbac_permissions")


@receiver(post_save, sender=TenantMembership)
@receiver(post_delete, sender=TenantMembership)
def invalidate_membership_permissions(sender, instance: TenantMembership, **kwargs):
    _invalidate_rbac_for_store(int(instance.tenant_id))


@receiver(post_save, sender=RolePermission)
@receiver(post_delete, sender=RolePermission)
@receiver(post_save, sender=Permission)
@receiver(post_delete, sender=Permission)
def invalidate_role_permission_changes(sender, **kwargs):
    for tenant_id in Tenant.objects.values_list("id", flat=True):
        _invalidate_rbac_for_store(int(tenant_id))

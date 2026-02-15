from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import AbstractBaseUser

from catalog.models import Product
from tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from tenants.domain.readiness import (
    StoreReadinessChecker,
    StoreReadinessResult,
    StoreReadinessSnapshot,
)
from tenants.models import StorePaymentSettings, StoreProfile, StoreShippingSettings, Tenant


@dataclass(frozen=True)
class GetStoreReadinessCommand:
    user: AbstractBaseUser
    tenant: Tenant


class GetStoreReadinessUseCase:
    @staticmethod
    def execute(cmd: GetStoreReadinessCommand) -> StoreReadinessResult:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=cmd.user, tenant=cmd.tenant)

        profile = StoreProfile.objects.filter(tenant=cmd.tenant).first()
        payment = StorePaymentSettings.objects.filter(tenant=cmd.tenant).first()
        shipping = StoreShippingSettings.objects.filter(tenant=cmd.tenant).first()

        active_products = Product.objects.filter(store_id=cmd.tenant.id, is_active=True).count()

        snapshot = StoreReadinessSnapshot(
            tenant_is_active=bool(getattr(cmd.tenant, "is_active", False)),
            store_info_completed=bool(getattr(profile, "store_info_completed", False)),
            setup_step=int(getattr(profile, "setup_step", 1) or 1),
            is_setup_complete=bool(getattr(profile, "is_setup_complete", False)),
            payment_mode=getattr(payment, "mode", None),
            payment_provider_name=getattr(payment, "provider_name", None),
            shipping_mode=getattr(shipping, "fulfillment_mode", None),
            shipping_origin_city=getattr(shipping, "origin_city", None),
            active_products_count=int(active_products or 0),
        )

        return StoreReadinessChecker.check(snapshot)


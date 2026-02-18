from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from apps.tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from apps.tenants.application.use_cases.store_setup_wizard import StoreSetupWizardUseCase
from apps.tenants.domain.setup_policies import validate_shipping_settings
from apps.tenants.models import StoreProfile, StoreShippingSettings, Tenant
from apps.tenants.services.audit_service import TenantAuditService


@dataclass(frozen=True)
class UpdateShippingSettingsCommand:
    user: AbstractBaseUser
    tenant: Tenant
    fulfillment_mode: str
    origin_city: str = ""
    delivery_fee_flat: Decimal | None = None
    free_shipping_threshold: Decimal | None = None
    is_enabled: bool = True


class UpdateShippingSettingsUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: UpdateShippingSettingsCommand) -> StoreShippingSettings:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=cmd.user, tenant=cmd.tenant)

        profile = StoreProfile.objects.select_for_update().filter(tenant=cmd.tenant).first()
        if not profile:
            profile = StoreProfile.objects.create(
                tenant=cmd.tenant,
                owner=cmd.user,
                store_info_completed=True,
                setup_step=StoreSetupWizardUseCase.STEP_PAYMENT,
                is_setup_complete=False,
            )

        state = StoreSetupWizardUseCase.get_state(profile=profile)
        if not profile.is_setup_complete and state.current_step < StoreSetupWizardUseCase.STEP_SHIPPING:
            raise ValueError("Complete payment setup before shipping setup.")

        data = validate_shipping_settings(
            fulfillment_mode=cmd.fulfillment_mode,
            origin_city=cmd.origin_city,
            delivery_fee_flat=cmd.delivery_fee_flat,
            free_shipping_threshold=cmd.free_shipping_threshold,
            is_enabled=cmd.is_enabled,
        )

        settings = StoreShippingSettings.objects.select_for_update().filter(tenant=cmd.tenant).first()
        if settings:
            settings.fulfillment_mode = data["fulfillment_mode"]
            settings.origin_city = data["origin_city"]
            settings.delivery_fee_flat = data["delivery_fee_flat"]
            settings.free_shipping_threshold = data["free_shipping_threshold"]
            settings.is_enabled = data["is_enabled"]
            settings.save()
        else:
            settings = StoreShippingSettings.objects.create(
                tenant=cmd.tenant,
                fulfillment_mode=data["fulfillment_mode"],
                origin_city=data["origin_city"],
                delivery_fee_flat=data["delivery_fee_flat"],
                free_shipping_threshold=data["free_shipping_threshold"],
                is_enabled=data["is_enabled"],
            )

        StoreSetupWizardUseCase.mark_step_done(user=cmd.user, profile=profile, step=3)

        TenantAuditService.record_action(
            cmd.tenant,
            "store_shipping_settings_updated",
            actor=getattr(cmd.user, "username", "user"),
            details="Shipping settings updated.",
            metadata={
                "fulfillment_mode": settings.fulfillment_mode,
                "origin_city": settings.origin_city,
                "is_enabled": settings.is_enabled,
            },
        )

        return settings


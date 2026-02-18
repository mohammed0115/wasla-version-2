from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from apps.tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from apps.tenants.application.use_cases.store_setup_wizard import StoreSetupWizardUseCase
from apps.tenants.domain.setup_policies import validate_payment_settings
from apps.tenants.models import StorePaymentSettings, StoreProfile, Tenant
from apps.tenants.services.audit_service import TenantAuditService


@dataclass(frozen=True)
class UpdatePaymentSettingsCommand:
    user: AbstractBaseUser
    tenant: Tenant
    payment_mode: str
    provider_name: str = ""
    merchant_key: str = ""
    webhook_secret: str = ""
    is_enabled: bool = True


class UpdatePaymentSettingsUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: UpdatePaymentSettingsCommand) -> StorePaymentSettings:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=cmd.user, tenant=cmd.tenant)

        data = validate_payment_settings(
            payment_mode=cmd.payment_mode,
            provider_name=cmd.provider_name,
            merchant_key=cmd.merchant_key,
            webhook_secret=cmd.webhook_secret,
            is_enabled=cmd.is_enabled,
        )

        profile = StoreProfile.objects.select_for_update().filter(tenant=cmd.tenant).first()
        if not profile:
            profile = StoreProfile.objects.create(
                tenant=cmd.tenant,
                owner=cmd.user,
                store_info_completed=True,
                setup_step=StoreSetupWizardUseCase.STEP_PAYMENT,
                is_setup_complete=False,
            )

        settings = StorePaymentSettings.objects.select_for_update().filter(tenant=cmd.tenant).first()
        if settings:
            settings.mode = data["payment_mode"]
            settings.provider_name = data["provider_name"]
            settings.merchant_key = data["merchant_key"]
            settings.webhook_secret = data["webhook_secret"]
            settings.is_enabled = data["is_enabled"]
            settings.save()
        else:
            settings = StorePaymentSettings.objects.create(
                tenant=cmd.tenant,
                mode=data["payment_mode"],
                provider_name=data["provider_name"],
                merchant_key=data["merchant_key"],
                webhook_secret=data["webhook_secret"],
                is_enabled=data["is_enabled"],
            )

        StoreSetupWizardUseCase.mark_step_done(user=cmd.user, profile=profile, step=2)

        TenantAuditService.record_action(
            cmd.tenant,
            "store_payment_settings_updated",
            actor=getattr(cmd.user, "username", "user"),
            details="Payment settings updated.",
            metadata={"mode": settings.mode, "provider_name": settings.provider_name, "is_enabled": settings.is_enabled},
        )

        return settings


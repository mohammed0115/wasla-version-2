from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from apps.tenants.models import StoreProfile, Tenant
from apps.tenants.services.audit_service import TenantAuditService


@dataclass(frozen=True)
class WizardState:
    current_step: int
    setup_completed: bool


class StoreSetupWizardUseCase:
    STEP_STORE_INFO = 1
    STEP_PAYMENT = 2
    STEP_SHIPPING = 3
    STEP_FIRST_PRODUCT = 4
    STEP_DONE = 4

    @staticmethod
    def get_state(*, profile: StoreProfile) -> WizardState:
        if profile.is_setup_complete:
            return WizardState(current_step=StoreSetupWizardUseCase.STEP_DONE, setup_completed=True)
        step = int(getattr(profile, "setup_step", 1) or 1)
        step = max(StoreSetupWizardUseCase.STEP_STORE_INFO, min(step, StoreSetupWizardUseCase.STEP_FIRST_PRODUCT))
        return WizardState(current_step=step, setup_completed=False)

    @staticmethod
    @transaction.atomic
    def mark_step_done(*, user, profile: StoreProfile, step: int) -> StoreProfile:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=user, tenant=profile.tenant)
        if profile.is_setup_complete:
            return profile

        if step < StoreSetupWizardUseCase.STEP_STORE_INFO or step > StoreSetupWizardUseCase.STEP_FIRST_PRODUCT:
            return profile

        profile.setup_step = max(int(profile.setup_step or 1), step + 1)
        if profile.setup_step > StoreSetupWizardUseCase.STEP_FIRST_PRODUCT:
            profile.setup_step = StoreSetupWizardUseCase.STEP_FIRST_PRODUCT
        profile.save(update_fields=["setup_step", "updated_at"])

        tenant = profile.tenant
        tenant.setup_step = max(int(tenant.setup_step or 1), profile.setup_step)
        if tenant.setup_step > StoreSetupWizardUseCase.STEP_FIRST_PRODUCT:
            tenant.setup_step = StoreSetupWizardUseCase.STEP_FIRST_PRODUCT
        tenant.save(update_fields=["setup_step", "updated_at"])

        TenantAuditService.record_action(
            tenant,
            "store_setup_step_done",
            actor=getattr(user, "username", "user"),
            details=f"Wizard step {step} marked done.",
            metadata={"step": step, "next_step": profile.setup_step},
        )
        return profile

    @staticmethod
    @transaction.atomic
    def complete_setup(*, user, profile: StoreProfile) -> StoreProfile:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=user, tenant=profile.tenant)
        if profile.is_setup_complete:
            return profile

        profile.is_setup_complete = True
        profile.setup_step = StoreSetupWizardUseCase.STEP_DONE
        profile.save(update_fields=["is_setup_complete", "setup_step", "updated_at"])

        tenant = profile.tenant
        tenant.setup_completed = True
        tenant.setup_completed_at = timezone.now()
        tenant.setup_step = StoreSetupWizardUseCase.STEP_DONE
        tenant.save(update_fields=["setup_completed", "setup_completed_at", "setup_step", "updated_at"])

        TenantAuditService.record_action(
            tenant,
            "store_setup_completed",
            actor=getattr(user, "username", "user"),
            details="Wizard completed.",
        )
        return profile

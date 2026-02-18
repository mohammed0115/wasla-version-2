from __future__ import annotations

from dataclasses import dataclass

from apps.tenants.application.use_cases.store_setup_wizard import StoreSetupWizardUseCase
from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.models import StoreProfile


@dataclass(frozen=True)
class SetupProgress:
    step: int
    percent: int
    label: str
    next_label: str


@dataclass(frozen=True)
class GetSetupProgressCommand:
    tenant_ctx: TenantContext
    actor_id: int | None


class GetSetupProgressUseCase:
    STEP_LABELS = {
        1: "Store info",
        2: "Payment",
        3: "Shipping",
        4: "Activate",
    }

    @staticmethod
    def execute(cmd: GetSetupProgressCommand) -> SetupProgress:
        profile = StoreProfile.objects.filter(tenant_id=cmd.tenant_ctx.tenant_id).first()
        if not profile:
            return SetupProgress(step=0, percent=0, label="Store info", next_label="Store info")

        state = StoreSetupWizardUseCase.get_state(profile=profile)
        step = StoreSetupWizardUseCase.STEP_FIRST_PRODUCT if profile.is_setup_complete else state.current_step
        step = max(1, min(int(step), 4))
        percent = int((step / 4) * 100)
        label = GetSetupProgressUseCase.STEP_LABELS.get(step, "Store info")
        next_step = min(step + 1, 4)
        next_label = GetSetupProgressUseCase.STEP_LABELS.get(next_step, label)
        return SetupProgress(step=step, percent=percent, label=label, next_label=next_label)

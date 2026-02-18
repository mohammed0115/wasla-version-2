from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils import timezone

from apps.tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from apps.tenants.application.use_cases.get_store_readiness import (
    GetStoreReadinessCommand,
    GetStoreReadinessUseCase,
)
from apps.tenants.application.use_cases.store_setup_wizard import StoreSetupWizardUseCase
from apps.tenants.domain.errors import StoreInactiveError, StoreNotReadyError
from apps.tenants.domain.readiness import StoreReadinessResult
from apps.tenants.models import StoreProfile, Tenant
from apps.tenants.services.audit_service import TenantAuditService


@dataclass(frozen=True)
class ActivateStoreCommand:
    user: AbstractBaseUser
    tenant: Tenant


@dataclass(frozen=True)
class ActivateStoreResult:
    tenant: Tenant
    readiness: StoreReadinessResult


class ActivateStoreUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: ActivateStoreCommand) -> ActivateStoreResult:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=cmd.user, tenant=cmd.tenant)

        tenant = Tenant.objects.select_for_update().get(id=cmd.tenant.id)
        if not tenant.is_active:
            raise StoreInactiveError("Store is inactive.")

        profile = StoreProfile.objects.select_for_update().filter(tenant=tenant).first()
        if not profile:
            raise StoreNotReadyError("Store profile not found.", reasons=["Store profile is missing."])

        readiness = GetStoreReadinessUseCase.execute(GetStoreReadinessCommand(user=cmd.user, tenant=tenant))
        if not readiness.ok:
            raise StoreNotReadyError("Store is not ready to activate.", reasons=list(readiness.errors))

        now = timezone.now()
        if not tenant.activated_at:
            tenant.activated_at = now
        tenant.is_published = True
        tenant.deactivated_at = None
        tenant.save(update_fields=["is_published", "activated_at", "deactivated_at", "updated_at"])

        if not profile.is_setup_complete:
            StoreSetupWizardUseCase.complete_setup(user=cmd.user, profile=profile)

        TenantAuditService.record_action(
            tenant,
            "store_activated",
            actor=getattr(cmd.user, "username", "user"),
            details="Store activated (published).",
            metadata={"activated_at": tenant.activated_at.isoformat() if tenant.activated_at else None},
        )

        return ActivateStoreResult(tenant=tenant, readiness=readiness)


@dataclass(frozen=True)
class DeactivateStoreCommand:
    user: AbstractBaseUser
    tenant: Tenant
    reason: str = ""


class DeactivateStoreUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: DeactivateStoreCommand) -> Tenant:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=cmd.user, tenant=cmd.tenant)

        tenant = Tenant.objects.select_for_update().get(id=cmd.tenant.id)
        if not tenant.is_published and tenant.deactivated_at:
            return tenant

        tenant.is_published = False
        tenant.deactivated_at = timezone.now()
        tenant.save(update_fields=["is_published", "deactivated_at", "updated_at"])

        TenantAuditService.record_action(
            tenant,
            "store_deactivated",
            actor=getattr(cmd.user, "username", "user"),
            details="Store deactivated (unpublished).",
            metadata={"reason": (cmd.reason or "").strip()},
        )

        return tenant


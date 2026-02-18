from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import AbstractBaseUser
from django.db import IntegrityError, transaction

from apps.subscriptions.models import SubscriptionPlan
from apps.subscriptions.services.subscription_service import SubscriptionService
from apps.tenants.domain.errors import (
    StoreSlugAlreadyTakenError,
)
from apps.tenants.domain.policies import validate_hex_color, validate_store_name, validate_tenant_slug
from apps.tenants.models import StoreProfile, Tenant, TenantMembership
from apps.tenants.services.audit_service import TenantAuditService


@dataclass(frozen=True)
class CreateStoreCommand:
    user: AbstractBaseUser
    name: str
    slug: str
    currency: str = "SAR"
    language: str = "ar"
    logo_file: object | None = None
    primary_color: str = ""
    secondary_color: str = ""


@dataclass(frozen=True)
class CreateStoreResult:
    tenant: Tenant
    created: bool


class CreateStoreUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: CreateStoreCommand) -> CreateStoreResult:
        if not getattr(cmd.user, "is_authenticated", False):
            raise ValueError("Authentication required.")

        existing_profile = (
            StoreProfile.objects.select_related("tenant")
            .filter(owner=cmd.user, tenant__is_active=True)
            .order_by("tenant_id")
            .first()
        )
        if existing_profile:
            return CreateStoreResult(tenant=existing_profile.tenant, created=False)

        existing_owned = (
            Tenant.objects.filter(
                memberships__user=cmd.user,
                memberships__role=TenantMembership.ROLE_OWNER,
                memberships__is_active=True,
            )
            .order_by("id")
            .first()
        )
        if existing_owned:
            return CreateStoreResult(tenant=existing_owned, created=False)

        store_name = validate_store_name(cmd.name)
        slug = validate_tenant_slug(cmd.slug)
        if Tenant.objects.filter(slug=slug).exists():
            raise StoreSlugAlreadyTakenError("This store slug is already taken.")

        primary_color = validate_hex_color(cmd.primary_color)
        secondary_color = validate_hex_color(cmd.secondary_color)

        tenant = Tenant.objects.create(
            slug=slug,
            name=store_name,
            is_active=True,
            currency=cmd.currency or "SAR",
            language=cmd.language or "ar",
            logo=cmd.logo_file if cmd.logo_file else None,
            primary_color=primary_color,
            secondary_color=secondary_color,
            setup_step=2,
            setup_completed=False,
        )

        try:
            TenantMembership.objects.create(
                tenant=tenant,
                user=cmd.user,
                role=TenantMembership.ROLE_OWNER,
                is_active=True,
            )
        except IntegrityError as exc:
            existing_owned = (
                Tenant.objects.filter(
                    memberships__user=cmd.user,
                    memberships__role=TenantMembership.ROLE_OWNER,
                    memberships__is_active=True,
                )
                .order_by("id")
                .first()
            )
            if existing_owned:
                return CreateStoreResult(tenant=existing_owned, created=False)
            raise ValueError("Failed to create store membership.") from exc

        try:
            StoreProfile.objects.create(
                tenant=tenant,
                owner=cmd.user,
                store_info_completed=True,
                setup_step=2,
                is_setup_complete=False,
            )
        except IntegrityError:
            StoreProfile.objects.update_or_create(
                owner=cmd.user,
                defaults={
                    "tenant": tenant,
                    "store_info_completed": True,
                    "setup_step": 2,
                    "is_setup_complete": False,
                },
            )

        basic_plan = SubscriptionPlan.objects.filter(name="Basic", is_active=True).first()
        if basic_plan:
            SubscriptionService.subscribe_store(tenant.id, basic_plan)

        TenantAuditService.record_action(
            tenant,
            "store_created",
            actor=getattr(cmd.user, "username", "user"),
            details="Store created via onboarding.",
            metadata={"slug": tenant.slug, "currency": tenant.currency, "language": tenant.language},
        )

        return CreateStoreResult(tenant=tenant, created=True)

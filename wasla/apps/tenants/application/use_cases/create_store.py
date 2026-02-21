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
from apps.stores.models import Store, StoreSettings, StoreSetupStep
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

        raw_name = (cmd.name or "").strip()
        if not raw_name:
            user_full_name = ""
            try:
                user_full_name = (cmd.user.get_full_name() or "").strip()
            except Exception:
                user_full_name = ""
            raw_name = (
                user_full_name
                or getattr(cmd.user, "first_name", "") or ""
            ).strip()
            if not raw_name:
                raw_name = (getattr(cmd.user, "username", "") or "").strip()
        if not raw_name:
            raw_name = "Merchant Store"
        store_name = validate_store_name(raw_name)
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
        if not tenant.subdomain:
            tenant.subdomain = slug
            tenant.save(update_fields=["subdomain"])

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

        store = Store.objects.filter(owner=cmd.user).order_by("id").first()
        if store and store.tenant_id is None:
            updates = []
            store.tenant = tenant
            updates.append("tenant")
            if not store.slug:
                store.slug = slug
                updates.append("slug")
            if not store.subdomain:
                store.subdomain = slug
                updates.append("subdomain")
            if store.status != Store.STATUS_ACTIVE:
                store.status = Store.STATUS_ACTIVE
                updates.append("status")
            if store.name != store_name and not store.name:
                store.name = store_name
                updates.append("name")
            store.save(update_fields=updates or None)
        elif not store:
            if Store.objects.filter(slug=slug).exists() or Store.objects.filter(subdomain=slug).exists():
                raise StoreSlugAlreadyTakenError("This store slug is already taken.")
            store = Store.objects.create(
                owner=cmd.user,
                tenant=tenant,
                name=store_name,
                slug=slug,
                subdomain=slug,
                status=Store.STATUS_ACTIVE,
            )
        if store:
            StoreSettings.objects.get_or_create(store=store)
            StoreSetupStep.objects.get_or_create(store=store)

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

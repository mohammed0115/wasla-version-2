from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.db.models import Q

from apps.tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from apps.tenants.domain.errors import StoreSlugAlreadyTakenError
from apps.tenants.domain.policies import validate_hex_color, validate_tenant_slug
from apps.tenants.models import Tenant
from apps.stores.models import Store
from apps.tenants.services.audit_service import TenantAuditService


@dataclass(frozen=True)
class UpdateStoreSettingsCommand:
    user: AbstractBaseUser
    tenant: Tenant
    name: str
    slug: str
    currency: str
    language: str
    logo_file: object | None = None
    primary_color: str = ""
    secondary_color: str = ""


class UpdateStoreSettingsUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: UpdateStoreSettingsCommand) -> Tenant:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=cmd.user, tenant=cmd.tenant)

        new_slug = validate_tenant_slug(cmd.slug)
        if (
            new_slug != cmd.tenant.slug
            and Tenant.objects.filter(slug=new_slug).exclude(id=cmd.tenant.id).exists()
        ):
            raise StoreSlugAlreadyTakenError("This store slug is already taken.")

        if new_slug != cmd.tenant.slug:
            conflict = Store.objects.filter(
                Q(slug=new_slug) | Q(subdomain=new_slug)
            ).exclude(tenant=cmd.tenant)
            if conflict.exists():
                raise StoreSlugAlreadyTakenError("This store slug is already taken.")

        primary_color = validate_hex_color(cmd.primary_color)
        secondary_color = validate_hex_color(cmd.secondary_color)

        before = {
            "name": cmd.tenant.name,
            "slug": cmd.tenant.slug,
            "currency": cmd.tenant.currency,
            "language": cmd.tenant.language,
            "primary_color": cmd.tenant.primary_color,
            "secondary_color": cmd.tenant.secondary_color,
        }

        old_slug = cmd.tenant.slug
        old_subdomain = (cmd.tenant.subdomain or "").strip().lower()

        cmd.tenant.name = (cmd.name or "").strip()
        cmd.tenant.slug = new_slug
        if not old_subdomain or old_subdomain == old_slug:
            cmd.tenant.subdomain = new_slug
        cmd.tenant.currency = (cmd.currency or "SAR").strip()
        cmd.tenant.language = (cmd.language or "ar").strip()
        if cmd.logo_file:
            cmd.tenant.logo = cmd.logo_file
        cmd.tenant.primary_color = primary_color
        cmd.tenant.secondary_color = secondary_color
        cmd.tenant.save()

        if new_slug != old_slug:
                store = Store.objects.filter(tenant=cmd.tenant).order_by("id").first()
            if store:
                store_slug = (store.slug or "").strip().lower()
                store_subdomain = (store.subdomain or "").strip().lower()
                should_sync = (
                    not store_slug
                    or not store_subdomain
                    or store_slug == old_slug
                    or store_subdomain == old_slug
                )
                if should_sync:
                    store.slug = new_slug
                    store.subdomain = new_slug
                    store.save(update_fields=["slug", "subdomain", "updated_at"])

        after = {
            "name": cmd.tenant.name,
            "slug": cmd.tenant.slug,
            "currency": cmd.tenant.currency,
            "language": cmd.tenant.language,
            "primary_color": cmd.tenant.primary_color,
            "secondary_color": cmd.tenant.secondary_color,
        }

        TenantAuditService.record_action(
            cmd.tenant,
            "store_settings_updated",
            actor=getattr(cmd.user, "username", "user"),
            details="Store settings updated.",
            metadata={"before": before, "after": after},
        )

        return cmd.tenant


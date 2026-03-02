from __future__ import annotations

from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.stores.models import Store
from apps.tenants.models import Tenant, StoreProfile, TenantMembership


class Command(BaseCommand):
    help = "Bootstrap the platform tenant and default store for the root domain."

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            type=str,
            default=None,
            help="Store slug (default: settings.DEFAULT_STORE_SLUG or 'store1')",
        )
        parser.add_argument(
            "--store-name",
            type=str,
            default="Platform Store",
            help="Store name (default: Platform Store)",
        )
        parser.add_argument(
            "--tenant-slug",
            type=str,
            default="platform",
            help="Tenant slug (default: platform)",
        )
        parser.add_argument(
            "--tenant-name",
            type=str,
            default="Platform",
            help="Tenant name (default: Platform)",
        )
        parser.add_argument(
            "--owner-username",
            type=str,
            default="",
            help="Owner username (optional; defaults to first active superuser)",
        )
        parser.add_argument(
            "--owner-email",
            type=str,
            default="",
            help="Owner email (optional; defaults to first active superuser)",
        )
        parser.add_argument(
            "--subdomain",
            type=str,
            default="",
            help="Store subdomain (default: store slug)",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Skip confirmation prompt",
        )

    def handle(self, *args, **options):
        slug = (options["slug"] or getattr(settings, "DEFAULT_STORE_SLUG", "store1") or "store1").strip()
        tenant_slug = (options["tenant_slug"] or "platform").strip()
        tenant_name = (options["tenant_name"] or "Platform").strip()
        store_name = (options["store_name"] or "Platform Store").strip()
        owner_username = (options["owner_username"] or "").strip()
        owner_email = (options["owner_email"] or "").strip()
        subdomain = (options["subdomain"] or slug).strip() or slug
        confirm = options["confirm"]

        owner = self._resolve_owner(owner_username, owner_email)
        if owner is None:
            self.stdout.write(self.style.ERROR("No suitable owner user found."))
            self.stdout.write(
                "Create or specify a superuser, or pass --owner-username/--owner-email."
            )
            return

        if not confirm:
            self.stdout.write("\nBootstrap Platform Store:")
            self.stdout.write(f"  Tenant: {tenant_slug} ({tenant_name})")
            self.stdout.write(f"  Store:  {store_name} (slug={slug}, subdomain={subdomain})")
            self.stdout.write(f"  Owner:  {owner.get_username()} (id={owner.id})")
            answer = input("\nProceed? [y/N]: ").strip().lower()
            if answer != "y":
                self.stdout.write(self.style.WARNING("Cancelled."))
                return

        with transaction.atomic():
            tenant, created = Tenant.objects.get_or_create(
                slug=tenant_slug,
                defaults={
                    "name": tenant_name,
                    "is_active": True,
                    "is_published": True,
                    "subdomain": tenant_slug,
                    "setup_step": 2,
                    "setup_completed": True,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"OK Created tenant {tenant.slug}"))
            else:
                changed = False
                if not tenant.name:
                    tenant.name = tenant_name
                    changed = True
                if not tenant.subdomain:
                    tenant.subdomain = tenant_slug
                    changed = True
                if not tenant.is_active:
                    tenant.is_active = True
                    changed = True
                if not tenant.is_published:
                    tenant.is_published = True
                    changed = True
                if changed:
                    tenant.save(update_fields=["name", "subdomain", "is_active", "is_published"])
                    self.stdout.write(self.style.SUCCESS(f"OK Updated tenant {tenant.slug}"))

            existing_store = Store.objects.filter(slug=slug).first()
            if existing_store:
                if existing_store.tenant_id != tenant.id:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Store '{slug}' already exists under a different tenant (id={existing_store.tenant_id})."
                        )
                    )
                    return
                self.stdout.write(self.style.WARNING(f"Store '{slug}' already exists; leaving as-is."))
                store = existing_store
            else:
                store_kwargs = {
                    "slug": slug,
                    "name": store_name,
                    "tenant": tenant,
                }
                try:
                    Store._meta.get_field("owner")
                    store_kwargs["owner"] = owner
                except FieldDoesNotExist:
                    pass
                try:
                    Store._meta.get_field("subdomain")
                    store_kwargs["subdomain"] = subdomain
                except FieldDoesNotExist:
                    pass
                try:
                    Store._meta.get_field("status")
                    store_kwargs["status"] = Store.STATUS_ACTIVE
                except FieldDoesNotExist:
                    try:
                        Store._meta.get_field("is_active")
                        store_kwargs["is_active"] = True
                    except FieldDoesNotExist:
                        pass

                store = Store.objects.create(**store_kwargs)
                self.stdout.write(self.style.SUCCESS(f"OK Created store {store.slug} (id={store.id})"))

            owner_membership = TenantMembership.objects.filter(
                user=owner,
                role=TenantMembership.ROLE_OWNER,
                is_active=True,
            ).exclude(tenant=tenant).first()
            if owner_membership:
                self.stdout.write(
                    self.style.WARNING(
                        "Owner already has an active owner membership on another tenant; "
                        "skipping owner membership creation."
                    )
                )
            else:
                TenantMembership.objects.get_or_create(
                    tenant=tenant,
                    user=owner,
                    defaults={"role": TenantMembership.ROLE_OWNER, "is_active": True},
                )

            existing_profile = StoreProfile.objects.filter(owner=owner).first()
            if existing_profile and existing_profile.tenant_id != tenant.id:
                self.stdout.write(
                    self.style.WARNING(
                        "Owner already has a StoreProfile for another tenant; skipping StoreProfile creation."
                    )
                )
            else:
                StoreProfile.objects.get_or_create(
                    tenant=tenant,
                    defaults={
                        "owner": owner,
                        "store_info_completed": True,
                        "setup_step": 2,
                        "is_setup_complete": True,
                    },
                )

        self.stdout.write(self.style.SUCCESS("Bootstrap complete."))

    def _resolve_owner(self, username: str, email: str) -> Optional[object]:
        User = get_user_model()
        if username:
            user = User.objects.filter(username=username, is_active=True).first()
            if user:
                return user
        if email:
            user = User.objects.filter(email=email, is_active=True).first()
            if user:
                return user
        return User.objects.filter(is_superuser=True, is_active=True).order_by("id").first()

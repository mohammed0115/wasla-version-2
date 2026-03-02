from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.stores.models import Store
from apps.tenants.models import StoreDomain, Tenant


class Command(BaseCommand):
    help = "Ensure platform tenant/store/domain mapping exists for the root domain."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-slug", type=str, default="")
        parser.add_argument("--tenant-name", type=str, default="Platform")
        parser.add_argument("--store-slug", type=str, default="")
        parser.add_argument("--store-name", type=str, default="Platform Store")
        parser.add_argument("--owner-username", type=str, default="")
        parser.add_argument("--owner-email", type=str, default="")

    def handle(self, *args, **options):
        base_domain = (getattr(settings, "WASSLA_BASE_DOMAIN", "w-sala.com") or "w-sala.com").strip().lower()
        tenant_slug = (options["tenant_slug"] or getattr(settings, "WASSLA_PLATFORM_TENANT_SLUG", "") or "platform").strip()
        tenant_name = (options["tenant_name"] or "Platform").strip()
        store_slug = (options["store_slug"] or getattr(settings, "WASSLA_PLATFORM_STORE_SLUG", "") or tenant_slug).strip()
        store_name = (options["store_name"] or "Platform Store").strip()

        owner = self._resolve_owner(options.get("owner_username", ""), options.get("owner_email", ""))
        if owner is None:
            self.stdout.write(self.style.ERROR("No suitable owner user found."))
            self.stdout.write("Create a superuser or provide --owner-username/--owner-email.")
            return

        actions: list[str] = []

        with transaction.atomic():
            store = Store.objects.filter(is_platform_default=True).first()

            if not store:
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
                    actions.append(f"Created tenant {tenant.slug}")
                else:
                    updates = {}
                    if not tenant.name:
                        updates["name"] = tenant_name
                    if not tenant.subdomain:
                        updates["subdomain"] = tenant_slug
                    if not tenant.is_active:
                        updates["is_active"] = True
                    if not tenant.is_published:
                        updates["is_published"] = True
                    if updates:
                        for key, value in updates.items():
                            setattr(tenant, key, value)
                        tenant.save(update_fields=list(updates.keys()))
                        actions.append(f"Updated tenant {tenant.slug}")

                store = Store.objects.filter(slug=store_slug).first()
                if store and store.tenant_id != tenant.id:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Store '{store_slug}' exists under another tenant (id={store.tenant_id})."
                        )
                    )
                    return

                if not store:
                    store_kwargs = {
                        "slug": store_slug,
                        "subdomain": store_slug,
                        "name": store_name,
                        "tenant": tenant,
                    }
                    try:
                        Store._meta.get_field("owner")
                        store_kwargs["owner"] = owner
                    except FieldDoesNotExist:
                        pass
                    try:
                        Store._meta.get_field("status")
                        store_kwargs["status"] = Store.STATUS_ACTIVE
                    except FieldDoesNotExist:
                        pass
                    store = Store.objects.create(**store_kwargs)
                    actions.append(f"Created store {store.slug}")

                if not store.subdomain:
                    store.subdomain = store_slug
                    store.save(update_fields=["subdomain"])
                    actions.append("Set store subdomain")

                store.is_platform_default = True
                store.save(update_fields=["is_platform_default"])
            else:
                if store.tenant_id is None:
                    tenant = Tenant.objects.get_or_create(
                        slug=tenant_slug,
                        defaults={"name": tenant_name, "is_active": True, "is_published": True},
                    )[0]
                    store.tenant = tenant
                    store.save(update_fields=["tenant"])
                    actions.append("Attached tenant to platform store")

            for host in {base_domain, f"www.{base_domain}"}:
                if not host:
                    continue
                domain, created = StoreDomain.objects.get_or_create(
                    domain=host,
                    defaults={
                        "tenant": store.tenant,
                        "store": store,
                        "status": StoreDomain.STATUS_ACTIVE,
                        "is_primary": True,
                        "verification_token": StoreDomain.generate_verification_token(),
                    },
                )
                if created:
                    actions.append(f"Created domain mapping {host}")
                else:
                    updates = {}
                    if domain.store_id is None:
                        updates["store_id"] = store.id
                    if domain.tenant_id is None and store.tenant_id:
                        updates["tenant_id"] = store.tenant_id
                    if not domain.verification_token:
                        updates["verification_token"] = StoreDomain.generate_verification_token()
                    if updates:
                        StoreDomain.objects.filter(id=domain.id).update(**updates)
                        actions.append(f"Updated domain mapping {host}")

        if not actions:
            self.stdout.write(self.style.SUCCESS("Platform store already configured."))
            return

        self.stdout.write(self.style.SUCCESS("Platform store ensured:"))
        for action in actions:
            self.stdout.write(f" - {action}")

    def _resolve_owner(self, username: str, email: str):
        User = get_user_model()
        username = (username or "").strip()
        email = (email or "").strip()
        if username:
            user = User.objects.filter(username=username, is_active=True).first()
            if user:
                return user
        if email:
            user = User.objects.filter(email=email, is_active=True).first()
            if user:
                return user
        return User.objects.filter(is_superuser=True, is_active=True).order_by("id").first()

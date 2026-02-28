from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.admin_portal.models import AdminRole, AdminUserRole
from apps.catalog.services.category_service import ensure_global_categories
from apps.subscriptions.models import SubscriptionPlan, StoreSubscription
from apps.tenants.application.use_cases.create_store import CreateStoreCommand, CreateStoreUseCase
from apps.tenants.domain.errors import StoreSlugAlreadyTakenError
from apps.tenants.models import StoreProfile, Tenant, TenantMembership
from apps.stores.models import Store


class Command(BaseCommand):
    help = "Seed demo data for Wasla merchant journey (admin, merchant, store, plans, categories)."

    def add_arguments(self, parser):
        parser.add_argument("--admin-username", default="admin")
        parser.add_argument("--admin-password", default="admin12345")
        parser.add_argument("--admin-email", default="admin@wasla.local")
        parser.add_argument("--merchant-username", default="merchant")
        parser.add_argument("--merchant-password", default="merchant12345")
        parser.add_argument("--merchant-email", default="merchant@wasla.local")
        parser.add_argument("--store-name", default="Wasla Demo Store")
        parser.add_argument("--store-slug", default="store1")

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()

        admin_user, created_admin = User.objects.get_or_create(
            username=options["admin_username"],
            defaults={
                "email": options["admin_email"],
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        if created_admin:
            admin_user.set_password(options["admin_password"])
            admin_user.save(update_fields=["password"])
        elif not admin_user.is_staff:
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save(update_fields=["is_staff", "is_superuser"])

        role, _ = AdminRole.objects.get_or_create(
            name="SuperAdmin",
            defaults={"description": "Full access"},
        )
        AdminUserRole.objects.get_or_create(user=admin_user, defaults={"role": role})

        merchant_user, created_merchant = User.objects.get_or_create(
            username=options["merchant_username"],
            defaults={
                "email": options["merchant_email"],
                "is_active": True,
                "is_staff": False,
            },
        )
        if created_merchant:
            merchant_user.set_password(options["merchant_password"])
            merchant_user.save(update_fields=["password"])

        # Ensure merchant profile has onboarding completed for quick access.
        try:
            profile = merchant_user.profile
            profile.persona_completed = True
            profile.save(update_fields=["persona_completed"])
        except Exception:
            pass

        # Seed subscription plans (only if missing).
        default_plans = [
            ("Basic", 0, "monthly", []),
            ("Pro", 199, "monthly", ["custom_domain", "ai_tools", "ai_visual_search", "tap", "stripe", "stc_pay"]),
            ("Business", 399, "monthly", ["custom_domain", "ai_tools", "ai_visual_search", "tap", "stripe", "stc_pay"]),
        ]
        for name, price, cycle, features in default_plans:
            SubscriptionPlan.objects.get_or_create(
                name=name,
                billing_cycle=cycle,
                defaults={"price": price, "features": features, "is_active": True},
            )

        ensure_global_categories()

        # Create tenant/store for merchant if missing.
        tenant = Tenant.objects.filter(memberships__user=merchant_user, memberships__is_active=True).first()
        if not tenant:
            try:
                result = CreateStoreUseCase.execute(
                    CreateStoreCommand(
                        user=merchant_user,
                        name=options["store_name"],
                        slug=options["store_slug"],
                    )
                )
                tenant = result.tenant
            except StoreSlugAlreadyTakenError:
                tenant = Tenant.objects.filter(slug=options["store_slug"]).first()
                if not tenant:
                    # fallback: generate a unique slug
                    base_slug = f"{options['store_slug']}-demo"
                    idx = 1
                    slug = base_slug
                    while Tenant.objects.filter(slug=slug).exists():
                        idx += 1
                        slug = f"{base_slug}-{idx}"
                    result = CreateStoreUseCase.execute(
                        CreateStoreCommand(
                            user=merchant_user,
                            name=options["store_name"],
                            slug=slug,
                        )
                    )
                    tenant = result.tenant

        # Ensure membership/profile
        membership = TenantMembership.objects.filter(tenant=tenant, user=merchant_user).first()
        if not membership:
            existing_owner = TenantMembership.objects.filter(
                tenant=tenant,
                role=TenantMembership.ROLE_OWNER,
                is_active=True,
            ).first()
            if not existing_owner:
                TenantMembership.objects.create(
                    tenant=tenant,
                    user=merchant_user,
                    role=TenantMembership.ROLE_OWNER,
                    is_active=True,
                )
        StoreProfile.objects.get_or_create(
            tenant=tenant,
            defaults={
                "owner": merchant_user,
                "store_info_completed": True,
                "setup_step": 2,
                "is_setup_complete": False,
            },
        )

        # Make store inactive/pending publish by default.
        Store.objects.filter(tenant_id=tenant.id).update(status=Store.STATUS_INACTIVE)
        Tenant.objects.filter(id=tenant.id).update(is_published=False)

        # Create a pending subscription to simulate unpaid flow.
        plan = SubscriptionPlan.objects.filter(name="Pro", is_active=True).first()
        if plan and not StoreSubscription.objects.filter(store_id=tenant.id).exists():
            StoreSubscription.objects.create(
                store_id=tenant.id,
                plan=plan,
                status="pending",
            )

        self.stdout.write(self.style.SUCCESS("Seeded demo data for Wasla."))
        self.stdout.write(f"Admin login: {admin_user.username} / {options['admin_password']}")
        self.stdout.write(f"Merchant login: {merchant_user.username} / {options['merchant_password']}")
        self.stdout.write(f"Store slug: {tenant.slug}")

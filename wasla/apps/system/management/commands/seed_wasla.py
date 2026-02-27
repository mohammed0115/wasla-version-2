from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.subscriptions.models import SubscriptionPlan
from apps.tenants.models import StoreProfile, Tenant, TenantMembership
from apps.tenants.services.provisioning import provision_store_after_payment


class Command(BaseCommand):
    help = "Safe Wasla seed: plans + optional superuser + optional demo merchant/store."

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-demo-store",
            action="store_true",
            help="Create demo merchant and provision a demo store.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self._seed_default_plans()
        self._seed_optional_superuser()

        if options.get("with_demo_store", False):
            self._seed_demo_store()

        self.stdout.write(self.style.SUCCESS("seed_wasla completed successfully."))

    def _seed_default_plans(self):
        if SubscriptionPlan.objects.exists():
            self.stdout.write("Subscription plans already exist; skipping default plan creation.")
            return

        defaults = [
            {
                "name": "Basic",
                "price": 0,
                "billing_cycle": "monthly",
                "features": [],
                "is_active": True,
            },
            {
                "name": "Plus",
                "price": 99,
                "billing_cycle": "monthly",
                "features": ["custom_domain"],
                "is_active": True,
            },
            {
                "name": "Pro",
                "price": 299,
                "billing_cycle": "monthly",
                "features": ["custom_domain", "ai_tools", "ai_visual_search"],
                "is_active": True,
            },
        ]
        SubscriptionPlan.objects.bulk_create([SubscriptionPlan(**payload) for payload in defaults])
        self.stdout.write(self.style.SUCCESS("Created default subscription plans."))

    def _seed_optional_superuser(self):
        username = (os.getenv("SEED_SUPERUSER_USERNAME") or "").strip()
        password = (os.getenv("SEED_SUPERUSER_PASSWORD") or "").strip()
        email = (os.getenv("SEED_SUPERUSER_EMAIL") or "").strip()

        if not (username and password):
            self.stdout.write("Superuser env vars not set; skipping superuser creation.")
            return

        UserModel = get_user_model()
        user = UserModel.objects.filter(username=username).first()
        if user:
            self.stdout.write(f"Superuser '{username}' already exists; skipping.")
            return

        UserModel.objects.create_superuser(
            username=username,
            password=password,
            email=email,
        )
        self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))

    def _seed_demo_store(self):
        UserModel = get_user_model()
        username = "demo_merchant"
        email = "demo_merchant@wasla.local"
        password = "demo12345"

        merchant, created = UserModel.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_active": True},
        )
        if created:
            merchant.set_password(password)
            merchant.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS("Created demo merchant user."))
        else:
            self.stdout.write("Demo merchant already exists; reusing.")

        profile = getattr(merchant, "profile", None)
        if profile is not None and not profile.persona_completed:
            profile.persona_completed = True
            profile.save(update_fields=["persona_completed"])

        tenant = (
            TenantMembership.objects.select_related("tenant")
            .filter(user=merchant, role=TenantMembership.ROLE_OWNER, is_active=True)
            .order_by("tenant_id")
            .first()
        )
        tenant_obj = tenant.tenant if tenant else None

        if tenant_obj is None:
            base_slug = "demo-store"
            slug = base_slug
            index = 1
            while Tenant.objects.filter(slug=slug).exists():
                index += 1
                slug = f"{base_slug}-{index}"

            tenant_obj = Tenant.objects.create(
                slug=slug,
                subdomain=slug,
                name="Demo Store",
                is_active=True,
                is_published=False,
                setup_step=1,
                setup_completed=False,
            )
            TenantMembership.objects.create(
                tenant=tenant_obj,
                user=merchant,
                role=TenantMembership.ROLE_OWNER,
                is_active=True,
            )
            StoreProfile.objects.get_or_create(
                tenant=tenant_obj,
                defaults={
                    "owner": merchant,
                    "store_info_completed": True,
                    "setup_step": 2,
                    "is_setup_complete": False,
                },
            )

        default_plan = SubscriptionPlan.objects.filter(is_active=True).order_by("price", "id").first()
        if default_plan is None:
            raise ValueError("No active subscription plan exists; run plan seeding first.")

        store = provision_store_after_payment(merchant=merchant, plan=default_plan)
        self.stdout.write(self.style.SUCCESS(f"Demo store ready: tenant={tenant_obj.slug}, store_id={store.id}"))

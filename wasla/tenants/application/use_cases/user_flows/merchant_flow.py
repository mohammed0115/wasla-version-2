from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from catalog.models import Product
from subscriptions.models import SubscriptionPlan
from subscriptions.services.subscription_service import SubscriptionService

from .base import FlowReport, FlowStepResult


class MerchantFlowValidator:
    name = "merchant_flow"

    def run(self, *, client: Client, tenant_slug: str) -> FlowReport:
        steps: list[FlowStepResult] = []
        headers = {"HTTP_X_TENANT": tenant_slug}

        login_step = self._login(client, tenant_slug)
        steps.append(login_step)
        if not login_step.ok:
            return FlowReport.from_steps(name=self.name, tenant_slug=tenant_slug, steps=steps)

        subscription_step = self._ensure_subscription(tenant_slug)
        steps.append(subscription_step)
        if not subscription_step.ok:
            return FlowReport.from_steps(name=self.name, tenant_slug=tenant_slug, steps=steps)

        create_product_step = self._create_product(client, tenant_slug, headers)
        steps.append(create_product_step)

        view_orders_step = self._view_orders(client, headers)
        steps.append(view_orders_step)

        return FlowReport.from_steps(name=self.name, tenant_slug=tenant_slug, steps=steps)

    @staticmethod
    def _login(client: Client, tenant_slug: str) -> FlowStepResult:
        User = get_user_model()
        user, _ = User.objects.get_or_create(
            username="merchant_flow_user",
            defaults={"email": "merchant_flow_user@example.com", "is_staff": False, "is_active": True},
        )
        if not (getattr(user, "email", "") or "").strip():
            user.email = "merchant_flow_user@example.com"
        user.set_password("merchant12345")
        user.save(update_fields=["password", "email"])

        logged_in = client.login(username="merchant_flow_user", password="merchant12345")
        if logged_in:
            from django.utils import timezone

            from accounts.models import AccountProfile
            from tenants.models import Tenant, TenantMembership

            tenant = Tenant.objects.filter(slug=tenant_slug, is_active=True).first()
            if tenant:
                TenantMembership.objects.get_or_create(
                    tenant=tenant,
                    user=user,
                    defaults={"role": TenantMembership.ROLE_OWNER, "is_active": True},
                )

            # Ensure the merchant can access dashboard pages (profile + onboarding completed).
            phone_suffix = uuid.uuid4().int % 10**7
            AccountProfile.objects.update_or_create(
                user=user,
                defaults={
                    "full_name": "Merchant Flow User",
                    "phone": f"050{phone_suffix:07d}",
                    "country": "SA",
                    "business_types": ["fashion"],
                    "accepted_terms_at": timezone.now(),
                },
            )
            return FlowStepResult("login", True)
        return FlowStepResult("login", False, "Failed to login via Django session auth.")

    @staticmethod
    def _ensure_subscription(tenant_slug: str) -> FlowStepResult:
        from tenants.models import Tenant

        tenant = Tenant.objects.filter(slug=tenant_slug, is_active=True).first()
        if not tenant:
            return FlowStepResult("ensure_subscription", False, "Tenant not found or inactive.")

        if SubscriptionService.get_active_subscription(tenant.id):
            return FlowStepResult("ensure_subscription", True)

        plan = SubscriptionPlan.objects.filter(is_active=True).order_by("price", "id").first()
        if not plan:
            return FlowStepResult(
                "ensure_subscription",
                False,
                "No active subscription plan found for merchant flow.",
            )

        SubscriptionService.subscribe_store(tenant.id, plan)
        return FlowStepResult("ensure_subscription", True)

    @staticmethod
    def _create_product(client: Client, tenant_slug: str, headers: dict[str, str]) -> FlowStepResult:
        response = client.get(reverse("web:product_create"), **headers)
        if response.status_code != 200:
            return FlowStepResult(
                "create_product_page",
                False,
                f"Product create page not accessible (status {response.status_code}).",
            )

        product_count = Product.objects.count()
        sku = f"FLOW-SKU-{uuid.uuid4().hex[:8].upper()}"
        payload = {
            "sku": sku,
            "name": "Flow Product",
            "price": "9.99",
            "quantity": 3,
        }
        response = client.post(reverse("web:product_create"), data=payload, follow=True, **headers)
        if response.status_code not in (200, 302):
            return FlowStepResult(
                "create_product_submit",
                False,
                f"Product create submit failed (status {response.status_code}).",
            )

        if Product.objects.count() <= product_count:
            return FlowStepResult(
                "create_product_submit",
                False,
                "Product was not created. Check subscription limits or validation errors.",
            )

        created = Product.objects.order_by("-id").first()
        if created and created.is_active:
            return FlowStepResult("publish_product", True)
        return FlowStepResult("publish_product", False, "Product was created but not active.")

    @staticmethod
    def _view_orders(client: Client, headers: dict[str, str]) -> FlowStepResult:
        response = client.get(reverse("web:order_list"), **headers)
        if response.status_code == 200:
            return FlowStepResult("view_orders", True)
        return FlowStepResult(
            "view_orders",
            False,
            f"Orders list not accessible (status {response.status_code}).",
        )

from __future__ import annotations

from typing import Iterable

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client

from apps.catalog.services.product_service import ProductService
from apps.customers.services.customer_service import CustomerService
from apps.subscriptions.models import SubscriptionPlan
from apps.subscriptions.services.subscription_service import SubscriptionService
from apps.tenants.models import Tenant

from .base import FlowReport, FlowStepResult


class BuyerFlowValidator:
    name = "buyer_flow"

    def run(self, *, client: Client, tenant_slug: str) -> FlowReport:
        steps: list[FlowStepResult] = []
        headers = {"HTTP_X_TENANT": tenant_slug}

        steps.extend(self._assert_expected_endpoints(client, headers))
        steps.append(self._assert_cart_endpoint(client, headers))
        steps.append(self._assert_checkout_endpoint(client, headers))
        steps.append(self._assert_order_api(client, tenant_slug, headers))

        return FlowReport.from_steps(name=self.name, tenant_slug=tenant_slug, steps=steps)

    @staticmethod
    def _assert_expected_endpoints(client: Client, headers: dict[str, str]) -> Iterable[FlowStepResult]:
        expected = [
            ("/store/", "browse_storefront_home"),
            ("/store/search/", "search_page"),
        ]
        for path, label in expected:
            response = client.get(path, **headers)
            if response.status_code == 200:
                yield FlowStepResult(label, True)
            elif response.status_code == 302:
                yield FlowStepResult(
                    label,
                    False,
                    f"{path} redirects to login; guest access not allowed.",
                )
            else:
                yield FlowStepResult(
                    label,
                    False,
                    f"Expected {path} to exist (status 200/302) but got {response.status_code}.",
                )

    @staticmethod
    def _assert_cart_endpoint(client: Client, headers: dict[str, str]) -> FlowStepResult:
        response = client.get("/store/cart/", **headers)
        if response.status_code == 200:
            return FlowStepResult("add_to_cart", True)
        return FlowStepResult(
            "add_to_cart",
            False,
            f"Cart endpoint missing or inaccessible (status {response.status_code}).",
        )

    @staticmethod
    def _assert_checkout_endpoint(client: Client, headers: dict[str, str]) -> FlowStepResult:
        response = client.get("/store/checkout/", **headers)
        if response.status_code == 200:
            return FlowStepResult("checkout_page", True)
        return FlowStepResult(
            "checkout_page",
            False,
            f"Checkout endpoint missing or inaccessible (status {response.status_code}).",
        )

    @staticmethod
    def _assert_order_api(client: Client, tenant_slug: str, headers: dict[str, str]) -> FlowStepResult:
        tenant = Tenant.objects.filter(slug=tenant_slug, is_active=True).first()
        if not tenant:
            return FlowStepResult("order_api", False, "Tenant not found or inactive.")

        plan = SubscriptionPlan.objects.filter(is_active=True).order_by("price", "id").first()
        if plan and not SubscriptionService.get_active_subscription(tenant.id):
            SubscriptionService.subscribe_store(tenant.id, plan)

        sku = f"BUYER-SKU-{uuid.uuid4().hex[:8].upper()}"
        product = ProductService.create_product(
            store_id=tenant.id,
            sku=sku,
            name="Buyer Flow Product",
            price=Decimal("19.99"),
            quantity=5,
        )

        User = get_user_model()
        user, _ = User.objects.get_or_create(username="buyer_flow_user", defaults={"is_active": True})
        client.force_login(user)

        try:
            customer = CustomerService.create_customer(
                email="buyer_flow@example.com",
                full_name="Buyer Flow",
                store_id=tenant.id,
            )
        except ValueError:
            customer = tenant.customer_set.filter(email="buyer_flow@example.com").first()

        if not customer:
            return FlowStepResult("order_api", False, "Failed to create or fetch customer.")

        payload = {"items": [{"product_id": product.id, "quantity": 1, "price": str(product.price)}]}
        response = client.post(
            f"/api/customers/{customer.id}/orders/create/",
            data=payload,
            content_type="application/json",
            **headers,
        )
        if response.status_code == 201:
            return FlowStepResult("order_api", True)
        return FlowStepResult(
            "order_api",
            False,
            f"Order API failed (status {response.status_code}): {response.content!s}",
        )

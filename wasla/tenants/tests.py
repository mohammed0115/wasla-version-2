from __future__ import annotations

from django.test import TestCase
from django.test import Client

from subscriptions.models import SubscriptionPlan
from tenants.models import Tenant
from tenants.application.use_cases.user_flows.buyer_flow import BuyerFlowValidator
from tenants.application.use_cases.user_flows.merchant_flow import MerchantFlowValidator
from apptenants.application.use_cases.user_flows.admin_flow import AdminFlowValidator


class FlowValidatorTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.tenant = Tenant.objects.create(
            slug="store1",
            name="Store 1",
            is_active=True,
            currency="SAR",
            language="ar",
        )
        SubscriptionPlan.objects.get_or_create(
            name="Basic",
            defaults={
                "price": "0.00",
                "billing_cycle": "monthly",
                "is_active": True,
                "max_products": 100,
                "max_orders_monthly": 100,
                "max_staff_users": 5,
            },
        )
        self.client = Client()

    def test_buyer_flow_fails_when_storefront_missing(self):
        report = BuyerFlowValidator().run(client=self.client, tenant_slug=self.tenant.slug)
        self.assertFalse(report.passed)
        self.assertTrue(report.reasons)

    def test_merchant_flow_passes(self):
        report = MerchantFlowValidator().run(client=self.client, tenant_slug=self.tenant.slug)
        self.assertTrue(report.passed)

    def test_admin_flow_passes_with_audit(self):
        report = AdminFlowValidator().run(client=self.client, tenant_slug=self.tenant.slug)
        self.assertTrue(report.passed)

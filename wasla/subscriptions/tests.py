import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from catalog.services.product_service import ProductService
from customers.models import Customer
from orders.services.order_service import OrderService
from subscriptions.models import StoreSubscription, SubscriptionPlan
from subscriptions.services.exceptions import (
    NoActiveSubscriptionError,
    SubscriptionFeatureNotAllowedError,
    SubscriptionLimitExceededError,
)
from subscriptions.services.entitlement_service import SubscriptionEntitlementService
from tenants.models import Tenant


class SubscriptionLimitEnforcementTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            slug=f"t-{uuid.uuid4().hex[:8]}",
            name="Test Tenant",
            is_active=True,
        )
        self.plan = SubscriptionPlan.objects.create(
            name=f"TestPlan-{uuid.uuid4().hex[:8]}",
            price=0,
            billing_cycle="monthly",
            features=["wallet"],
            max_products=1,
            max_orders_monthly=1,
            max_staff_users=1,
            is_active=True,
        )
        StoreSubscription.objects.create(
            store_id=self.tenant.id,
            plan=self.plan,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            status="active",
        )

    def test_product_limit_is_enforced(self):
        ProductService.create_product(
            store_id=self.tenant.id,
            sku="SKU-1",
            name="P1",
            price=Decimal("1.00"),
            quantity=1,
        )
        with self.assertRaises(SubscriptionLimitExceededError):
            ProductService.create_product(
                store_id=self.tenant.id,
                sku="SKU-2",
                name="P2",
                price=Decimal("1.00"),
                quantity=1,
            )

    def test_orders_monthly_limit_is_enforced(self):
        product = ProductService.create_product(
            store_id=self.tenant.id,
            sku="SKU-1",
            name="P1",
            price=Decimal("10.00"),
            quantity=1,
        )
        customer = Customer.objects.create(
            store_id=self.tenant.id,
            email=f"customer-{uuid.uuid4()}@example.com",
            full_name="Customer",
        )
        OrderService.create_order(
            customer,
            [{"product": product, "quantity": 1, "price": product.price}],
            store_id=self.tenant.id,
        )
        with self.assertRaises(SubscriptionLimitExceededError):
            OrderService.create_order(
                customer,
                [{"product": product, "quantity": 1, "price": product.price}],
                store_id=self.tenant.id,
            )

    def test_no_subscription_blocks_product_create(self):
        tenant = Tenant.objects.create(
            slug=f"t-{uuid.uuid4().hex[:8]}",
            name="No Sub Tenant",
            is_active=True,
        )
        with self.assertRaises(NoActiveSubscriptionError):
            ProductService.create_product(
                store_id=tenant.id,
                sku="SKU-1",
                name="P1",
                price=Decimal("1.00"),
                quantity=1,
            )


class FeatureGatingTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            slug=f"ft-{uuid.uuid4().hex[:8]}",
            name="Feature Tenant",
            is_active=True,
        )
        self.plan = SubscriptionPlan.objects.create(
            name=f"FeaturePlan-{uuid.uuid4().hex[:8]}",
            price=0,
            billing_cycle="monthly",
            features=["ai_tools"],
            is_active=True,
        )
        StoreSubscription.objects.create(
            store_id=self.tenant.id,
            plan=self.plan,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            status="active",
        )

    def test_feature_gate_allows_enabled_feature(self):
        SubscriptionEntitlementService.assert_feature_enabled(self.tenant.id, "ai_tools")

    def test_feature_gate_blocks_missing_feature(self):
        with self.assertRaises(SubscriptionFeatureNotAllowedError):
            SubscriptionEntitlementService.assert_feature_enabled(self.tenant.id, "advanced_ai")

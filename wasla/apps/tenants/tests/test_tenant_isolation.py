from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from apps.customers.models import Customer
from apps.orders.models import Order
from apps.stores.models import Store
from apps.tenants.managers import (
    set_current_tenant_context,
    reset_current_tenant_context,
    tenant_bypass,
)
from apps.tenants.models import Tenant


class TestTenantIsolation(TestCase):
    def setUp(self):
        self.client = Client()
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="owner", password="pass123")

        self.tenant_a = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.tenant_b = Tenant.objects.create(slug="tenant-b", name="Tenant B")

        self.store_a = Store.objects.create(
            owner=self.owner,
            tenant=self.tenant_a,
            name="Store A",
            slug="store-a",
            subdomain="store-a",
            status=Store.STATUS_ACTIVE,
        )
        self.store_b = Store.objects.create(
            owner=self.owner,
            tenant=self.tenant_b,
            name="Store B",
            slug="store-b",
            subdomain="store-b",
            status=Store.STATUS_ACTIVE,
        )

        self.customer_a = Customer.objects.create(
            store_id=self.store_a.id,
            email="a@example.com",
            full_name="Customer A",
        )
        self.customer_b = Customer.objects.create(
            store_id=self.store_b.id,
            email="b@example.com",
            full_name="Customer B",
        )

        self.order_a = Order.objects.create(
            store_id=self.store_a.id,
            tenant_id=self.tenant_a.id,
            order_number="ORD-A",
            customer=self.customer_a,
            total_amount=Decimal("100.00"),
            currency="SAR",
            payment_status="pending",
            status="pending",
        )
        self.order_b = Order.objects.create(
            store_id=self.store_b.id,
            tenant_id=self.tenant_b.id,
            order_number="ORD-B",
            customer=self.customer_b,
            total_amount=Decimal("200.00"),
            currency="SAR",
            payment_status="pending",
            status="pending",
        )

    def test_query_requires_tenant_context(self):
        with self.assertRaises(ImproperlyConfigured):
            list(Order.objects.all())

    def test_queryset_scoped_by_tenant_context(self):
        token = set_current_tenant_context(tenant_id=self.tenant_a.id, store_id=self.store_a.id, bypass=False)
        try:
            orders = list(Order.objects.all())
        finally:
            reset_current_tenant_context(token)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].id, self.order_a.id)

    def test_superadmin_bypass_allows_global_query(self):
        with tenant_bypass():
            orders = list(Order.objects.all())
        self.assertEqual({o.id for o in orders}, {self.order_a.id, self.order_b.id})

    def test_save_rejects_cross_tenant_assignment(self):
        token = set_current_tenant_context(tenant_id=self.tenant_a.id, store_id=self.store_a.id, bypass=False)
        try:
            with self.assertRaises(ValueError):
                Order.objects.create(
                    store_id=self.store_b.id,
                    tenant_id=self.tenant_b.id,
                    order_number="ORD-LEAK",
                    customer=self.customer_a,
                    total_amount=Decimal("50.00"),
                    currency="SAR",
                    payment_status="pending",
                    status="pending",
                )
        finally:
            reset_current_tenant_context(token)

    def test_guard_blocks_api_without_tenant(self):
        response = self.client.get("/api/shipping/shipments/")
        self.assertEqual(response.status_code, 404)

    def test_guard_allows_admin_portal(self):
        response = self.client.get("/admin-portal/login/")
        self.assertIn(response.status_code, {200, 302})

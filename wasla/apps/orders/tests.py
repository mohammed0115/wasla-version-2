from __future__ import annotations

import uuid
from decimal import Decimal

from django.test import TestCase
from django.test.utils import override_settings
from django.contrib.auth import get_user_model

from apps.catalog.models import Product
from apps.customers.models import Customer
from apps.orders.models import Order
from apps.orders.services.order_lifecycle_service import OrderLifecycleService
from apps.orders.services.order_service import OrderService
from apps.shipping.models import Shipment
from apps.stores.models import Store
from apps.tenants.infrastructure.repositories.django_order_repository import DjangoOrderRepository
from apps.tenants.models import Tenant
from apps.wallet.models import Wallet


class OrderLifecycleServiceTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.tenant = Tenant.objects.create(slug="tenant-1", name="Tenant 1", is_active=True)
        self.store = Store.objects.create(
            owner=get_user_model().objects.create_user(username="owner1", password="pass12345"),
            tenant=self.tenant,
            name="Store 1",
            slug="store-1",
            subdomain="store-1",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        self.store_id = self.store.id
        self.customer = Customer.objects.create(
            store_id=self.store_id,
            email="c@example.com",
            full_name="Customer",
            group="retail",
            is_active=True,
        )
        self.product = Product.objects.create(
            store_id=self.store_id,
            sku="SKU-1",
            name="Product",
            price="10.00",
            is_active=True,
        )

    def _create_order(self, *, status: str) -> Order:
        return Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store_id,
            order_number=str(uuid.uuid4())[:12],
            customer=self.customer,
            status=status,
            total_amount=Decimal("25.00"),
        )

    def test_invalid_transition_raises(self):
        order = self._create_order(status="pending")
        with self.assertRaisesMessage(ValueError, "Invalid status transition."):
            OrderLifecycleService.transition(order=order, new_status="processing")

    def test_create_order_sets_tenant(self):
        order = OrderService.create_order(
            self.customer,
            items=[{"product": self.product, "quantity": 1, "price": Decimal("10.00")}],
            store_id=self.store_id,
            tenant_id=self.tenant.id,
        )
        self.assertEqual(order.tenant_id, self.store_id)
        first_item = order.items.first()
        self.assertIsNotNone(first_item)
        self.assertEqual(first_item.tenant_id, self.store_id)

    def test_delivered_requires_shipment(self):
        order = self._create_order(status="shipped")
        with self.assertRaisesMessage(ValueError, "Cannot mark delivered/completed without a shipment."):
            OrderLifecycleService.transition(order=order, new_status="delivered")

    def test_delivered_updates_shipments_except_cancelled(self):
        order = self._create_order(status="shipped")
        shipped = Shipment.objects.create(order=order, carrier="dhl", status="shipped", tenant_id=self.tenant.id)
        cancelled = Shipment.objects.create(order=order, carrier="dhl", status="cancelled", tenant_id=self.tenant.id)

        OrderLifecycleService.transition(order=order, new_status="delivered")

        shipped.refresh_from_db()
        cancelled.refresh_from_db()
        order.refresh_from_db()

        self.assertEqual(order.status, "delivered")
        self.assertEqual(shipped.status, "delivered")
        self.assertEqual(cancelled.status, "cancelled")

    def test_completed_credits_wallet_once(self):
        order = self._create_order(status="delivered")
        Shipment.objects.create(order=order, carrier="dhl", status="delivered", tenant_id=self.tenant.id)
        wallet = Wallet.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store_id,
            balance="0.00",
            currency="USD",
            is_active=True,
        )

        OrderLifecycleService.transition(order=order, new_status="completed")
        wallet.refresh_from_db()
        self.assertEqual(str(wallet.balance), "25.00")

        order.status = "delivered"
        order.save(update_fields=["status"])
        OrderLifecycleService.transition(order=order, new_status="completed")
        wallet.refresh_from_db()
        self.assertEqual(str(wallet.balance), "25.00")


class OrderRepositoryTenantIsolationTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = DjangoOrderRepository()
        self.tenant_a = Tenant.objects.create(slug="tenant-a", name="Tenant A", is_active=True)
        self.tenant_b = Tenant.objects.create(slug="tenant-b", name="Tenant B", is_active=True)
        owner = get_user_model().objects.create_user(username="owner-repo", password="pass12345")
        self.store_a = Store.objects.create(
            owner=owner,
            tenant=self.tenant_a,
            name="Store A",
            slug="store-a",
            subdomain="store-a",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        self.store_b = Store.objects.create(
            owner=owner,
            tenant=self.tenant_b,
            name="Store B",
            slug="store-b",
            subdomain="store-b",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        self.store_a_id = self.store_a.id
        self.store_b_id = self.store_b.id
        self.customer_a = Customer.objects.create(
            store_id=self.store_a_id,
            email="a@example.com",
            full_name="Customer A",
            group="retail",
            is_active=True,
        )
        self.customer_b = Customer.objects.create(
            store_id=self.store_b_id,
            email="b@example.com",
            full_name="Customer B",
            group="retail",
            is_active=True,
        )

    def test_metrics_are_scoped_to_tenant_store_id(self):
        order_a = Order.objects.create(
            tenant_id=self.tenant_a.id,
            store_id=self.store_a_id,
            order_number=str(uuid.uuid4())[:12],
            customer=self.customer_a,
            status="paid",
            total_amount=Decimal("30.00"),
        )
        Order.objects.create(
            tenant_id=self.tenant_b.id,
            store_id=self.store_b_id,
            order_number=str(uuid.uuid4())[:12],
            customer=self.customer_b,
            status="paid",
            total_amount=Decimal("90.00"),
        )

        self.assertEqual(self.repo.count_orders_today(self.store_a_id, "UTC"), 1)
        self.assertEqual(self.repo.sum_sales_today(self.store_a_id, "UTC"), Decimal("30.00"))
        recent = self.repo.recent_orders(self.store_a_id)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["id"], order_a.id)


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", ".localhost"])
class OrderTenantIsolationAPITests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        User = get_user_model()
        self.user = User.objects.create_user(username="staff", password="pass12345")
        self.client.force_login(self.user)

        self.tenant_a = Tenant.objects.create(slug="tenant-a-api", name="Tenant A", is_active=True)
        self.tenant_b = Tenant.objects.create(slug="tenant-b-api", name="Tenant B", is_active=True)
        self.store_a = Store.objects.create(
            owner=self.user,
            tenant=self.tenant_a,
            name="Store A",
            slug="storea",
            subdomain="storea",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        self.store_b = Store.objects.create(
            owner=self.user,
            tenant=self.tenant_b,
            name="Store B",
            slug="storeb",
            subdomain="storeb",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

        self.customer_a = Customer.objects.create(
            store_id=self.store_a.id,
            email="a@example.com",
            full_name="Customer A",
            group="retail",
            is_active=True,
        )
        self.customer_b = Customer.objects.create(
            store_id=self.store_b.id,
            email="b@example.com",
            full_name="Customer B",
            group="retail",
            is_active=True,
        )
        self.product_a = Product.objects.create(
            store_id=self.store_a.id,
            sku="SKU-A",
            name="Product A",
            price="10.00",
            is_active=True,
        )
        self.product_b = Product.objects.create(
            store_id=self.store_b.id,
            sku="SKU-B",
            name="Product B",
            price="15.00",
            is_active=True,
        )

        self.order_a = Order.objects.create(
            tenant_id=self.tenant_a.id,
            store_id=self.store_a.id,
            order_number="ORDER-A",
            customer=self.customer_a,
            status="paid",
            total_amount=Decimal("25.00"),
            customer_name="Customer A",
            customer_email="a@example.com",
        )
        self.order_b = Order.objects.create(
            tenant_id=self.tenant_b.id,
            store_id=self.store_b.id,
            order_number="ORDER-B",
            customer=self.customer_b,
            status="paid",
            total_amount=Decimal("30.00"),
            customer_name="Customer B",
            customer_email="b@example.com",
        )

    def test_orders_list_isolation_via_exports(self):
        response = self.client.get("/api/exports/orders.csv", HTTP_HOST="storeb.localhost")
        self.assertEqual(response.status_code, 200)
        csv_bytes = b"".join(response.streaming_content)
        csv_text = csv_bytes.decode("utf-8")
        self.assertIn("ORDER-B", csv_text)
        self.assertNotIn("ORDER-A", csv_text)

    def test_order_detail_isolation_via_invoice_export(self):
        response = self.client.get(
            f"/api/exports/invoice/{self.order_a.id}.pdf",
            HTTP_HOST="storeb.localhost",
        )
        self.assertEqual(response.status_code, 404)

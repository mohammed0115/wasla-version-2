from __future__ import annotations

import uuid
from decimal import Decimal

from django.test import TestCase

from catalog.models import Product
from customers.models import Customer
from orders.models import Order
from orders.services.order_lifecycle_service import OrderLifecycleService
from shipping.models import Shipment
from tenants.infrastructure.repositories.django_order_repository import DjangoOrderRepository
from wallet.models import Wallet


class OrderLifecycleServiceTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.store_id = 1
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

    def test_delivered_requires_shipment(self):
        order = self._create_order(status="shipped")
        with self.assertRaisesMessage(ValueError, "Cannot mark delivered/completed without a shipment."):
            OrderLifecycleService.transition(order=order, new_status="delivered")

    def test_delivered_updates_shipments_except_cancelled(self):
        order = self._create_order(status="shipped")
        shipped = Shipment.objects.create(order=order, carrier="dhl", status="shipped")
        cancelled = Shipment.objects.create(order=order, carrier="dhl", status="cancelled")

        OrderLifecycleService.transition(order=order, new_status="delivered")

        shipped.refresh_from_db()
        cancelled.refresh_from_db()
        order.refresh_from_db()

        self.assertEqual(order.status, "delivered")
        self.assertEqual(shipped.status, "delivered")
        self.assertEqual(cancelled.status, "cancelled")

    def test_completed_credits_wallet_once(self):
        order = self._create_order(status="delivered")
        Shipment.objects.create(order=order, carrier="dhl", status="delivered")
        wallet = Wallet.objects.create(store_id=self.store_id, balance="0.00", currency="USD", is_active=True)

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
        self.store_a = 101
        self.store_b = 202
        self.customer_a = Customer.objects.create(
            store_id=self.store_a,
            email="a@example.com",
            full_name="Customer A",
            group="retail",
            is_active=True,
        )
        self.customer_b = Customer.objects.create(
            store_id=self.store_b,
            email="b@example.com",
            full_name="Customer B",
            group="retail",
            is_active=True,
        )

    def test_metrics_are_scoped_to_tenant_store_id(self):
        order_a = Order.objects.create(
            store_id=self.store_a,
            order_number=str(uuid.uuid4())[:12],
            customer=self.customer_a,
            status="paid",
            total_amount=Decimal("30.00"),
        )
        Order.objects.create(
            store_id=self.store_b,
            order_number=str(uuid.uuid4())[:12],
            customer=self.customer_b,
            status="paid",
            total_amount=Decimal("90.00"),
        )

        self.assertEqual(self.repo.count_orders_today(self.store_a, "UTC"), 1)
        self.assertEqual(self.repo.sum_sales_today(self.store_a, "UTC"), Decimal("30.00"))
        recent = self.repo.recent_orders(self.store_a)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["id"], order_a.id)

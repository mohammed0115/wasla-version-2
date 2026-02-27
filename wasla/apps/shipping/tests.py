from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings

from apps.customers.models import Customer
from apps.orders.models import Order
from apps.shipping.models import Shipment
from apps.stores.models import Store
from apps.tenants.models import Tenant


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", ".localhost"])
class ShippingApiTests(TestCase):
	def setUp(self) -> None:
		super().setUp()
		user_model = get_user_model()
		self.user = user_model.objects.create_user(username="shipping-user", password="pass12345")
		self.client.force_login(self.user)

		self.tenant_a = Tenant.objects.create(slug="ship-tenant-a", name="Ship Tenant A", is_active=True)
		self.tenant_b = Tenant.objects.create(slug="ship-tenant-b", name="Ship Tenant B", is_active=True)

		self.store_a = Store.objects.create(
			owner=self.user,
			tenant=self.tenant_a,
			name="Ship Store A",
			slug="shipa",
			subdomain="shipa",
			status=Store.STATUS_ACTIVE,
			country="SA",
		)
		self.store_b = Store.objects.create(
			owner=self.user,
			tenant=self.tenant_b,
			name="Ship Store B",
			slug="shipb",
			subdomain="shipb",
			status=Store.STATUS_ACTIVE,
			country="SA",
		)

		self.customer_a = Customer.objects.create(
			store_id=self.store_a.id,
			email="sa@example.com",
			full_name="Ship Customer A",
			group="retail",
			is_active=True,
		)
		self.customer_b = Customer.objects.create(
			store_id=self.store_b.id,
			email="sb@example.com",
			full_name="Ship Customer B",
			group="retail",
			is_active=True,
		)

		self.order_a = Order.objects.create(
			tenant_id=self.tenant_a.id,
			store_id=self.store_a.id,
			order_number=str(uuid.uuid4())[:12],
			customer=self.customer_a,
			status="shipped",
			total_amount=Decimal("30.00"),
		)
		self.order_b = Order.objects.create(
			tenant_id=self.tenant_b.id,
			store_id=self.store_b.id,
			order_number=str(uuid.uuid4())[:12],
			customer=self.customer_b,
			status="shipped",
			total_amount=Decimal("40.00"),
		)

		self.shipment_a = Shipment.objects.create(
			order=self.order_a,
			carrier="courier_basic",
			status="shipped",
			tracking_number="A-TRACK-1",
			tenant_id=self.tenant_a.id,
		)
		self.shipment_b = Shipment.objects.create(
			order=self.order_b,
			carrier="courier_express",
			status="shipped",
			tracking_number="B-TRACK-1",
			tenant_id=self.tenant_b.id,
		)

	def test_shipments_list_is_store_scoped(self):
		response = self.client.get("/api/shipping/shipments/", HTTP_HOST="shipa.localhost")
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(len(payload), 1)
		self.assertEqual(payload[0]["id"], self.shipment_a.id)
		self.assertEqual(payload[0]["tracking_number"], "A-TRACK-1")

	def test_shipment_detail_is_store_scoped(self):
		response = self.client.get(f"/api/shipping/shipments/{self.shipment_a.id}/", HTTP_HOST="shipa.localhost")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["id"], self.shipment_a.id)

		blocked = self.client.get(f"/api/shipping/shipments/{self.shipment_b.id}/", HTTP_HOST="shipa.localhost")
		self.assertEqual(blocked.status_code, 404)

	def test_status_update_delivered_updates_order(self):
		response = self.client.patch(
			f"/api/shipping/shipments/{self.shipment_a.id}/status/",
			data={"status": "delivered"},
			content_type="application/json",
			HTTP_HOST="shipa.localhost",
		)
		self.assertEqual(response.status_code, 200)

		self.shipment_a.refresh_from_db()
		self.order_a.refresh_from_db()
		self.assertEqual(self.shipment_a.status, "delivered")
		self.assertEqual(self.order_a.status, "delivered")

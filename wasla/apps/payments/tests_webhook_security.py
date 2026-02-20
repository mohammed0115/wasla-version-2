from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.catalog.models import Inventory, Product
from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem
from apps.payments.models import PaymentAttempt, PaymentProviderSettings, WebhookEvent
from apps.stores.models import Store
from apps.tenants.models import Tenant


class PaymentWebhookSecurityTests(APITestCase):
    def setUp(self) -> None:
        self.tenant = Tenant.objects.create(slug="d2-tenant", name="D2 Tenant")
        owner = get_user_model().objects.create_user(username="d2-owner", password="pass12345")
        self.store = Store.objects.create(
            owner=owner,
            tenant=self.tenant,
            name="D2 Store",
            slug="d2-store",
            subdomain="d2-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        self.order = self._create_order()
        self.provider_settings = PaymentProviderSettings.objects.create(
            store=self.store,
            tenant=self.tenant,
            provider="tap",
            provider_code="tap",
            public_key="pk_test",
            secret_key="sk_test",
            webhook_secret="d2-secret",
            is_active=True,
            mode="sandbox",
            is_enabled=True,
        )
        self.attempt = PaymentAttempt.objects.create(
            store=self.store,
            order=self.order,
            provider="tap",
            method="card",
            amount=self.order.total_amount,
            currency="SAR",
            status=PaymentAttempt.STATUS_CREATED,
            provider_reference="tap_ref_123",
            idempotency_key="d2-idem-001",
        )

    def test_invalid_webhook_secret_rejected(self):
        payload = {
            "event_id": "evt-invalid-1",
            "provider_reference": self.attempt.provider_reference,
            "status": "captured",
            "store_id": self.store.id,
        }

        response = self.client.post(
            "/api/payments/webhooks/tap/",
            data=payload,
            format="json",
            HTTP_X_WASLA_WEBHOOK_SECRET="wrong-secret",
        )

        self.assertEqual(response.status_code, 400)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, PaymentAttempt.STATUS_CREATED)
        self.assertEqual(WebhookEvent.objects.count(), 0)

    def test_webhook_idempotent_double_post(self):
        payload = {
            "event_id": "evt-paid-1",
            "provider_reference": self.attempt.provider_reference,
            "status": "captured",
            "store_id": self.store.id,
        }

        first = self.client.post(
            "/api/payments/webhooks/tap/",
            data=payload,
            format="json",
            HTTP_X_WASLA_WEBHOOK_SECRET="d2-secret",
        )
        second = self.client.post(
            "/api/payments/webhooks/tap/",
            data=payload,
            format="json",
            HTTP_X_WASLA_WEBHOOK_SECRET="d2-secret",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, PaymentAttempt.STATUS_PAID)

        self.assertEqual(WebhookEvent.objects.count(), 1)
        event = WebhookEvent.objects.get(provider="tap", event_id="evt-paid-1")
        self.assertEqual(event.status, WebhookEvent.STATUS_PROCESSED)

        second_data = second.json()
        self.assertTrue(second_data.get("success"))
        self.assertTrue(second_data["data"].get("idempotent"))

    def _create_order(self) -> Order:
        customer = Customer.objects.create(
            store_id=self.store.id,
            email="buyer-d2@example.com",
            full_name="Buyer D2",
        )
        product = Product.objects.create(
            store_id=self.store.id,
            sku="D2-SKU-1",
            name="D2 Product",
            price=Decimal("100.00"),
            description_ar="",
            description_en="",
        )
        Inventory.objects.create(product=product, quantity=10, in_stock=True)
        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number="D2-ORDER-1",
            customer=customer,
            total_amount=Decimal("100.00"),
            currency="SAR",
            status="pending",
            payment_status="pending",
        )
        OrderItem.objects.create(
            tenant_id=self.tenant.id,
            order=order,
            product=product,
            quantity=1,
            price=Decimal("100.00"),
        )
        return order

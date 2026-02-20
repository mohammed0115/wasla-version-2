from __future__ import annotations

import json
from decimal import Decimal

from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.catalog.models import Product, Inventory
from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem
from apps.payments.application.use_cases.handle_webhook_event import (
    HandleWebhookEventCommand,
    HandleWebhookEventUseCase,
)
from apps.payments.infrastructure.webhooks.signatures import compute_hmac_signature
from apps.payments.models import (
    Payment,
    PaymentEvent,
    PaymentIntent,
    PaymentProviderSettings,
)
from apps.settlements.models import LedgerEntry
from apps.stores.models import Store
from apps.tenants.models import StorePaymentSettings, StoreProfile, Tenant
from apps.webhooks.models import WebhookEvent


class PaymentWebhookIdempotencyTests(TestCase):
    def setUp(self) -> None:
        self.tenant = Tenant.objects.create(slug="tenant-1", name="Tenant 1")
        owner = get_user_model().objects.create_user(username="owner-pay-1", password="pass12345")
        self.store = Store.objects.create(
            owner=owner,
            tenant=self.tenant,
            name="Store 1",
            slug="store-1",
            subdomain="store-1",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        StorePaymentSettings.objects.create(
            tenant=self.tenant,
            mode=StorePaymentSettings.MODE_DUMMY,
            is_enabled=True,
        )
        PaymentProviderSettings.objects.create(
            tenant=self.tenant,
            provider_code="dummy",
            display_name="Dummy",
            is_enabled=True,
            webhook_secret="dummy-secret",
            credentials={},
        )
        self.order = self._create_order(store_id=self.store.id)
        self.intent = PaymentIntent.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order=self.order,
            provider_code="dummy",
            amount=self.order.total_amount,
            currency=self.order.currency,
            status="pending",
            provider_reference="REF-123",
            idempotency_key=f"dummy:{self.order.id}",
        )

    def test_webhook_idempotency_on_success(self):
        payload = {
            "event_id": "evt-1",
            "intent_reference": self.intent.provider_reference,
            "status": "succeeded",
        }
        raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        signature = compute_hmac_signature("dummy-secret", raw_body)
        cmd = HandleWebhookEventCommand(
            provider_code="dummy",
            headers={"X-Signature": signature},
            payload=payload,
            raw_body=raw_body,
        )

        event_first = HandleWebhookEventUseCase.execute(cmd)
        event_second = HandleWebhookEventUseCase.execute(cmd)

        self.assertEqual(event_first.id, event_second.id)
        self.assertEqual(WebhookEvent.objects.count(), 1)
        self.assertEqual(PaymentEvent.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(LedgerEntry.objects.count(), 1)

        self.intent.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.intent.status, "succeeded")
        self.assertEqual(self.order.payment_status, "paid")
        payment = Payment.objects.first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.tenant_id, self.tenant.id)
        self.assertEqual(self.intent.tenant_id, self.tenant.id)

    def test_webhook_rejects_invalid_signature(self):
        payload = {
            "event_id": "evt-bad",
            "intent_reference": self.intent.provider_reference,
            "status": "succeeded",
        }
        raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        cmd = HandleWebhookEventCommand(
            provider_code="dummy",
            headers={"X-Signature": "bad"},
            payload=payload,
            raw_body=raw_body,
        )

        with self.assertRaises(ValueError):
            HandleWebhookEventUseCase.execute(cmd)

        event = WebhookEvent.objects.filter(provider_code="dummy", event_id="evt-bad").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.processing_status, WebhookEvent.STATUS_FAILED)
        self.assertEqual(event.payload_raw, raw_body)

        self.intent.refresh_from_db()
        self.assertEqual(self.intent.status, "pending")

    def _create_order(self, *, store_id: int) -> Order:
        customer = Customer.objects.create(
            store_id=store_id,
            email="buyer@example.com",
            full_name="Buyer",
        )
        product = Product.objects.create(
            store_id=store_id,
            sku="SKU-1",
            name="Product",
            price=Decimal("100.00"),
            description_ar="",
            description_en="",
        )
        Inventory.objects.create(product=product, quantity=10, in_stock=True)
        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=store_id,
            order_number="ORDER-1",
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


class PaymentWebhookAPITests(APITestCase):
    def setUp(self) -> None:
        self.tenant = Tenant.objects.create(slug="api-tenant", name="API Tenant")
        owner = get_user_model().objects.create_user(username="owner-pay-2", password="pass12345")
        self.store = Store.objects.create(
            owner=owner,
            tenant=self.tenant,
            name="API Store",
            slug="api-store",
            subdomain="api-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        StorePaymentSettings.objects.create(
            tenant=self.tenant,
            mode=StorePaymentSettings.MODE_DUMMY,
            is_enabled=True,
        )
        for provider_code in ["dummy", "sandbox"]:
            PaymentProviderSettings.objects.create(
                tenant=self.tenant,
                provider_code=provider_code,
                display_name=provider_code.title(),
                is_enabled=True,
                webhook_secret=f"{provider_code}-secret",
                credentials={},
            )
        self.order = self._create_order(store_id=self.store.id)
        self.intent = PaymentIntent.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order=self.order,
            provider_code="dummy",
            amount=self.order.total_amount,
            currency=self.order.currency,
            status="pending",
            provider_reference="DUMMY-API-123",
            idempotency_key=f"dummy:api:{self.order.id}",
        )

    def test_webhook_api_endpoint_success(self):
        payload = {
            "event_id": "evt-api-1",
            "intent_reference": self.intent.provider_reference,
            "status": "succeeded",
        }
        raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        signature = compute_hmac_signature("dummy-secret", raw_body)
        
        response = self.client.post(
            "/api/payments/webhooks/dummy",
            data=payload,
            format="json",
            HTTP_X_SIGNATURE=signature,
        )
        
        self.assertEqual(response.status_code, 200)
        resp_data = response.json()
        self.assertTrue(resp_data.get("success"))
        self.assertEqual(resp_data["data"]["processing_status"], WebhookEvent.STATUS_PROCESSED)
        
        self.intent.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.intent.status, "succeeded")
        self.assertEqual(self.order.payment_status, "paid")

    def test_webhook_api_endpoint_invalid_signature(self):
        payload = {
            "event_id": "evt-api-bad",
            "intent_reference": self.intent.provider_reference,
            "status": "succeeded",
        }
        
        response = self.client.post(
            "/api/payments/webhooks/dummy",
            data=payload,
            format="json",
            HTTP_X_SIGNATURE="invalid",
        )
        
        self.assertEqual(response.status_code, 400)
        resp_data = response.json()
        self.assertFalse(resp_data.get("success"))

    def test_webhook_api_sandbox_provider(self):
        sandbox_intent = PaymentIntent.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order=self.order,
            provider_code="sandbox",
            amount=self.order.total_amount,
            currency=self.order.currency,
            status="pending",
            provider_reference="SANDBOX-API-456",
            idempotency_key=f"sandbox:api:{self.order.id}",
        )
        
        payload = {
            "event_id": "evt-sandbox-1",
            "intent_reference": sandbox_intent.provider_reference,
            "status": "succeeded",
        }
        raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        signature = compute_hmac_signature("sandbox-secret", raw_body)
        
        response = self.client.post(
            "/api/payments/webhooks/sandbox",
            data=payload,
            format="json",
            HTTP_X_SIGNATURE=signature,
        )
        
        self.assertEqual(response.status_code, 200)
        resp_data = response.json()
        self.assertTrue(resp_data.get("success"))
        
        sandbox_intent.refresh_from_db()
        self.assertEqual(sandbox_intent.status, "succeeded")

    def _create_order(self, *, store_id: int) -> Order:

        customer = Customer.objects.create(
            store_id=store_id,
            email="buyer@example.com",
            full_name="Buyer",
        )
        product = Product.objects.create(
            store_id=store_id,
            sku="SKU-1",
            name="Product",
            price=Decimal("100.00"),
            description_ar="",
            description_en="",
        )
        Inventory.objects.create(product=product, quantity=10, in_stock=True)
        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=store_id,
            order_number="ORDER-1",
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


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", ".localhost"])
class PaymentMerchantAccessTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(username="merchant-a", password="pass12345")
        self.other_user = User.objects.create_user(username="merchant-b", password="pass12345")
        self.tenant_a = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.tenant_b = Tenant.objects.create(slug="tenant-b", name="Tenant B")
        self.store_a = Store.objects.create(
            owner=self.user,
            tenant=self.tenant_a,
            name="Store A",
            slug="store-a",
            subdomain="store-a",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        self.store_b = Store.objects.create(
            owner=self.other_user,
            tenant=self.tenant_b,
            name="Store B",
            slug="store-b",
            subdomain="store-b",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        StoreProfile.objects.create(tenant=self.tenant_a, owner=self.user)
        StoreProfile.objects.create(tenant=self.tenant_b, owner=self.other_user)
        for tenant in (self.tenant_a, self.tenant_b):
            StorePaymentSettings.objects.create(
                tenant=tenant,
                mode=StorePaymentSettings.MODE_DUMMY,
                is_enabled=True,
            )
            PaymentProviderSettings.objects.create(
                tenant=tenant,
                provider_code="dummy",
                display_name="Dummy",
                is_enabled=True,
                webhook_secret="dummy-secret",
                credentials={},
            )
        self.order_a = self._create_order(store_id=self.store_a.id, tenant_id=self.tenant_a.id)
        self.order_b = self._create_order(store_id=self.store_b.id, tenant_id=self.tenant_b.id)

    def test_anonymous_cannot_access_merchant_payment_api(self):
        payload = {
            "order_id": self.order_b.id,
            "provider_code": "dummy",
            "return_url": "https://example.com/return",
        }
        response = self.client.post(
            "/api/payments/initiate",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_HOST=f"{self.store_b.slug}.localhost",
        )
        self.assertEqual(response.status_code, 403)

    def test_store_a_merchant_access_ok(self):
        self.client.force_login(self.user)
        payload = {
            "order_id": self.order_a.id,
            "provider_code": "dummy",
            "return_url": "https://example.com/return",
        }
        response = self.client.post(
            "/api/payments/initiate",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_HOST=f"{self.store_a.slug}.localhost",
        )
        self.assertEqual(response.status_code, 201)

    def test_store_b_merchant_cannot_access_store_a_by_host(self):
        self.client.force_login(self.other_user)
        payload = {
            "order_id": self.order_a.id,
            "provider_code": "dummy",
            "return_url": "https://example.com/return",
        }
        response = self.client.post(
            "/api/payments/initiate",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_HOST=f"{self.store_a.slug}.localhost",
        )
        self.assertEqual(response.status_code, 403)

    def _create_order(self, *, store_id: int, tenant_id: int) -> Order:
        customer = Customer.objects.create(
            store_id=store_id,
            email="buyer@example.com",
            full_name="Buyer",
        )
        product = Product.objects.create(
            store_id=store_id,
            sku=f"SKU-{store_id}",
            name="Product",
            price=Decimal("100.00"),
            description_ar="",
            description_en="",
        )
        Inventory.objects.create(product=product, quantity=10, in_stock=True)
        order = Order.objects.create(
            tenant_id=tenant_id,
            store_id=store_id,
            order_number=f"ORDER-{store_id}",
            customer=customer,
            total_amount=Decimal("100.00"),
            currency="SAR",
            status="pending",
            payment_status="pending",
        )
        OrderItem.objects.create(
            tenant_id=tenant_id,
            order=order,
            product=product,
            quantity=1,
            price=Decimal("100.00"),
        )
        return order

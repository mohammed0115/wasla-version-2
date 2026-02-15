from __future__ import annotations

import json
from decimal import Decimal

from django.test import TestCase

from catalog.models import Product, Inventory
from customers.models import Customer
from orders.models import Order, OrderItem
from payments.application.use_cases.handle_webhook_event import (
    HandleWebhookEventCommand,
    HandleWebhookEventUseCase,
)
from payments.infrastructure.webhooks.signatures import compute_hmac_signature
from payments.models import (
    Payment,
    PaymentEvent,
    PaymentIntent,
    PaymentProviderSettings,
)
from settlements.models import LedgerEntry
from tenants.models import StorePaymentSettings, Tenant
from webhooks.models import WebhookEvent


class PaymentWebhookIdempotencyTests(TestCase):
    def setUp(self) -> None:
        self.tenant = Tenant.objects.create(slug="store-1", name="Store 1")
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
        self.order = self._create_order(store_id=self.tenant.id)
        self.intent = PaymentIntent.objects.create(
            store_id=self.tenant.id,
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
            store_id=store_id,
            order_number="ORDER-1",
            customer=customer,
            total_amount=Decimal("100.00"),
            currency="SAR",
            status="pending",
            payment_status="pending",
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=1,
            price=Decimal("100.00"),
        )
        return order

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.catalog.models import Inventory, Product
from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem
from apps.payments.models import PaymentAttempt, PaymentProviderSettings
from apps.settlements.models import SettlementRecord
from apps.stores.models import Store
from apps.tenants.models import Tenant


class SettlementEngineWebhookTests(APITestCase):
    def setUp(self) -> None:
        self.tenant = Tenant.objects.create(slug="settle-tenant", name="Settlement Tenant")
        owner = get_user_model().objects.create_user(username="settle-owner", password="pass12345")
        self.store = Store.objects.create(
            owner=owner,
            tenant=self.tenant,
            name="Settlement Store",
            slug="settlement-store",
            subdomain="settlement-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        self.order = self._create_order()

        PaymentProviderSettings.objects.create(
            store=self.store,
            tenant=self.tenant,
            provider="tap",
            provider_code="tap",
            public_key="pk_test",
            secret_key="sk_test",
            webhook_secret="settlement-secret",
            is_active=True,
            mode="sandbox",
            is_enabled=True,
        )

        self.payment_attempt = PaymentAttempt.objects.create(
            store=self.store,
            order=self.order,
            provider="tap",
            method="card",
            amount=Decimal("100.00"),
            currency="SAR",
            status=PaymentAttempt.STATUS_CREATED,
            provider_reference="tap_settlement_ref_1",
            idempotency_key="settlement-idempotency-1",
        )

    def test_webhook_success_creates_one_settlement(self):
        payload = {
            "event_id": "evt-settlement-1",
            "provider_reference": self.payment_attempt.provider_reference,
            "status": "captured",
            "store_id": self.store.id,
        }

        response = self.client.post(
            "/api/payments/webhooks/tap/",
            data=payload,
            format="json",
            HTTP_X_WASLA_WEBHOOK_SECRET="settlement-secret",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SettlementRecord.objects.count(), 1)

    def test_duplicate_webhook_does_not_create_second_settlement(self):
        payload = {
            "event_id": "evt-settlement-dup",
            "provider_reference": self.payment_attempt.provider_reference,
            "status": "captured",
            "store_id": self.store.id,
        }

        self.client.post(
            "/api/payments/webhooks/tap/",
            data=payload,
            format="json",
            HTTP_X_WASLA_WEBHOOK_SECRET="settlement-secret",
        )
        self.client.post(
            "/api/payments/webhooks/tap/",
            data=payload,
            format="json",
            HTTP_X_WASLA_WEBHOOK_SECRET="settlement-secret",
        )

        self.assertEqual(SettlementRecord.objects.count(), 1)

    def test_settlement_values_gross_fee_net(self):
        payload = {
            "event_id": "evt-settlement-values",
            "provider_reference": self.payment_attempt.provider_reference,
            "status": "captured",
            "store_id": self.store.id,
        }

        response = self.client.post(
            "/api/payments/webhooks/tap/",
            data=payload,
            format="json",
            HTTP_X_WASLA_WEBHOOK_SECRET="settlement-secret",
        )
        self.assertEqual(response.status_code, 200)

        settlement = SettlementRecord.objects.get(payment_attempt=self.payment_attempt)
        self.assertEqual(settlement.gross_amount, Decimal("100.00"))
        self.assertEqual(settlement.wasla_fee, Decimal("1.00"))
        self.assertEqual(settlement.net_amount, Decimal("99.00"))

    def _create_order(self) -> Order:
        customer = Customer.objects.create(
            store_id=self.store.id,
            email="settlement-buyer@example.com",
            full_name="Settlement Buyer",
        )
        product = Product.objects.create(
            store_id=self.store.id,
            sku="SETTLE-SKU-1",
            name="Settlement Product",
            price=Decimal("100.00"),
            description_ar="",
            description_en="",
        )
        Inventory.objects.create(product=product, quantity=10, in_stock=True)
        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number="SETTLE-ORDER-1",
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

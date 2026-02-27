import json
import os
import time
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.customers.models import Customer
from apps.orders.models import Order
from apps.payments.application.use_cases.handle_webhook_event import (
    HandleWebhookEventCommand,
    HandleWebhookEventUseCase,
)
from apps.payments.application.use_cases.initiate_payment import (
    InitiatePaymentCommand,
    InitiatePaymentUseCase,
)
from apps.payments.infrastructure.webhooks.signatures import compute_stripe_signature
from apps.payments.models import PaymentIntent, PaymentProviderSettings
from apps.stores.models import Store
from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.models import StorePaymentSettings, Tenant


def _resolve_stripe_env():
    api_key_env = "STRIPE_TEST_API_KEY" if os.getenv("STRIPE_TEST_API_KEY") else "STRIPE_API_KEY"
    webhook_env = (
        "STRIPE_TEST_WEBHOOK_SECRET"
        if os.getenv("STRIPE_TEST_WEBHOOK_SECRET")
        else "STRIPE_WEBHOOK_SECRET"
    )
    api_key = os.getenv(api_key_env, "")
    webhook_secret = os.getenv(webhook_env, "")
    if not api_key or not api_key.startswith("sk_test"):
        pytest.skip("Stripe test secret key not configured (set STRIPE_TEST_API_KEY).")
    if not webhook_secret:
        pytest.skip("Stripe webhook secret not configured (set STRIPE_TEST_WEBHOOK_SECRET).")
    return api_key_env, webhook_env


class TestStripeIntegration(TestCase):
    def setUp(self):
        api_key_env, webhook_env = _resolve_stripe_env()

        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="stripe-merchant",
            password="pass123",
            is_staff=True,
        )
        self.tenant = Tenant.objects.create(slug="tenant-stripe", name="Tenant Stripe")
        self.store = Store.objects.create(
            owner=self.owner,
            tenant=self.tenant,
            name="Stripe Store",
            slug="stripe-store",
            subdomain="stripe-store",
            status=Store.STATUS_ACTIVE,
        )
        StorePaymentSettings.objects.create(
            tenant=self.tenant,
            mode=StorePaymentSettings.MODE_GATEWAY,
            is_enabled=True,
        )
        PaymentProviderSettings.objects.create(
            store=self.store,
            tenant=self.tenant,
            provider="stripe",
            provider_code="stripe",
            is_enabled=True,
            is_active=True,
            credentials={
                "api_key_env": api_key_env,
                "webhook_secret_env": webhook_env,
            },
        )
        self.customer = Customer.objects.create(
            store_id=self.store.id,
            email="stripe.customer@example.com",
            full_name="Stripe Customer",
        )
        self.order = Order.objects.create(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            order_number="STRIPE-1000",
            customer=self.customer,
            total_amount=Decimal("25.00"),
            currency="USD",
            payment_status="pending",
            status="pending",
        )
        self.tenant_ctx = TenantContext(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            currency="USD",
            user_id=self.owner.id,
            session_key="stripe-session",
        )

    def test_create_payment_intent(self):
        cmd = InitiatePaymentCommand(
            tenant_ctx=self.tenant_ctx,
            order_id=self.order.id,
            provider_code="stripe",
            return_url="https://merchant.example.com/return",
            idempotency_key="stripe:test:pi-create",
        )

        result = InitiatePaymentUseCase.execute(cmd)
        self.assertTrue(result.client_secret)

        intent = PaymentIntent.objects.filter(order=self.order).first()
        self.assertIsNotNone(intent)
        self.assertTrue(intent.provider_reference.startswith("pi_"))

    def test_webhook_succeeded_updates_intent(self):
        intent = PaymentIntent.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order=self.order,
            provider_code="stripe",
            idempotency_key="stripe:test:webhook-intent",
            provider_reference="pi_test_123",
            amount=self.order.total_amount,
            currency=self.order.currency,
            status="pending",
        )

        payload = {
            "id": "evt_test_123",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": intent.provider_reference}},
        }
        raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        timestamp = int(time.time())

        webhook_secret = os.getenv("STRIPE_TEST_WEBHOOK_SECRET") or os.getenv("STRIPE_WEBHOOK_SECRET")
        signature = compute_stripe_signature(
            secret=webhook_secret,
            timestamp=timestamp,
            payload=raw_body,
        )
        headers = {"Stripe-Signature": f"t={timestamp},v1={signature}"}

        cmd = HandleWebhookEventCommand(
            provider_code="stripe",
            headers=headers,
            payload=payload,
            raw_body=raw_body,
        )
        HandleWebhookEventUseCase.execute(cmd)

        intent.refresh_from_db()
        self.assertEqual(intent.status, "succeeded")

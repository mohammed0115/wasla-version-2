from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stores.models import Store
from apps.tenants.models import Tenant
from apps.subscriptions.models import SubscriptionPlan, StoreSubscription, PaymentTransaction
from apps.subscriptions.services.payment_transaction_service import PaymentTransactionService


class ManualPaymentWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="merchant", password="pass123")
        self.tenant = Tenant.objects.create(slug="merchant-store", name="Merchant Store", is_active=True)
        self.store = Store.objects.create(
            owner=self.user,
            tenant=self.tenant,
            name="Merchant Store",
            slug="merchant-store",
            subdomain="merchant-store",
            status=Store.STATUS_DRAFT,
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Basic",
            price=Decimal("0.00"),
            billing_cycle="monthly",
            is_active=True,
        )

    def test_manual_payment_paid_activates_subscription_and_store(self):
        tx = PaymentTransactionService.record_manual_payment(
            tenant=self.tenant,
            plan=self.plan,
            amount=Decimal("120.00"),
            reference="REF-001",
            status=PaymentTransaction.STATUS_PAID,
            recorded_by=self.user,
        )

        subscription = StoreSubscription.objects.filter(store_id=self.tenant.id, status="active").first()
        self.store.refresh_from_db()

        self.assertIsNotNone(tx)
        self.assertIsNotNone(subscription)
        self.assertEqual(tx.subscription_id, subscription.id)
        self.assertEqual(self.store.status, Store.STATUS_ACTIVE)

    def test_manual_payment_pending_does_not_activate_subscription(self):
        PaymentTransactionService.record_manual_payment(
            tenant=self.tenant,
            plan=self.plan,
            amount=Decimal("120.00"),
            reference="REF-002",
            status=PaymentTransaction.STATUS_PENDING,
            recorded_by=self.user,
        )

        subscription = StoreSubscription.objects.filter(store_id=self.tenant.id, status="active").first()
        self.store.refresh_from_db()

        self.assertIsNone(subscription)
        self.assertEqual(self.store.status, Store.STATUS_DRAFT)

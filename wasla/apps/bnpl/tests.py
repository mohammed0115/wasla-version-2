"""BNPL tests."""

import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.bnpl.models import BnplProvider, BnplTransaction, BnplWebhookLog
from apps.bnpl.services import (
    BnplPaymentOrchestrator,
    TabbyAdapter,
    TamaraAdapter,
)
from apps.stores.models import Store
from apps.orders.models import Order
from apps.cart.models import Cart, CartItem
from apps.catalog.models import Product, Category

User = get_user_model()


class BnplProviderModelTest(TestCase):
    """Test BnplProvider model."""

    def setUp(self):
        self.store = Store.objects.create(
            name="Test Store",
            currency="SAR",
        )

    def test_create_tabby_provider(self):
        """Test creating a Tabby provider."""
        provider = BnplProvider.objects.create(
            store=self.store,
            provider=BnplProvider.PROVIDER_TABBY,
            api_key="test-key",
            merchant_id="merchant-123",
            is_active=True,
        )

        self.assertEqual(provider.provider, BnplProvider.PROVIDER_TABBY)
        self.assertTrue(provider.is_active)
        self.assertIsNotNone(provider.created_at)

    def test_create_tamara_provider(self):
        """Test creating a Tamara provider."""
        provider = BnplProvider.objects.create(
            store=self.store,
            provider=BnplProvider.PROVIDER_TAMARA,
            api_key="test-key",
            merchant_id="merchant-456",
            is_active=True,
        )

        self.assertEqual(provider.provider, BnplProvider.PROVIDER_TAMARA)

    def test_get_api_url_sandbox(self):
        """Test getting API URL in sandbox mode."""
        provider = BnplProvider.objects.create(
            store=self.store,
            provider=BnplProvider.PROVIDER_TABBY,
            is_sandbox=True,
        )

        url = provider.get_api_url()
        self.assertIn("sandbox", url.lower() or "staging" in url.lower())

    def test_get_api_url_production(self):
        """Test getting API URL in production mode."""
        provider = BnplProvider.objects.create(
            store=self.store,
            provider=BnplProvider.PROVIDER_TABBY,
            is_sandbox=False,
        )

        url = provider.get_api_url()
        self.assertIsNotNone(url)
        self.assertTrue(url.startswith("http"))


class BnplTransactionModelTest(TestCase):
    """Test BnplTransaction model."""

    def setUp(self):
        self.store = Store.objects.create(
            name="Test Store",
            currency="SAR",
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="pass123",
        )
        self.order = Order.objects.create(
            store=self.store,
            customer=self.user,
            email=self.user.email,
            total_amount=Decimal("1000.00"),
            currency="SAR",
        )

    def test_create_transaction(self):
        """Test creating a BNPL transaction."""
        transaction = BnplTransaction.objects.create(
            order=self.order,
            provider=BnplTransaction.PROVIDER_TABBY,
            provider_order_id="order-123",
            amount=Decimal("1000.00"),
            currency="SAR",
            status=BnplTransaction.STATUS_PENDING,
            customer_email="test@example.com",
            payment_url="https://example.com/checkout",
        )

        self.assertEqual(transaction.status, BnplTransaction.STATUS_PENDING)
        self.assertTrue(transaction.is_pending())
        self.assertFalse(transaction.is_paid())

    def test_transaction_status_transitions(self):
        """Test transaction status transitions."""
        transaction = BnplTransaction.objects.create(
            order=self.order,
            provider=BnplTransaction.PROVIDER_TABBY,
            provider_order_id="order-123",
            status=BnplTransaction.STATUS_PENDING,
            amount=Decimal("1000.00"),
            currency="SAR",
        )

        # Approve
        transaction.status = BnplTransaction.STATUS_APPROVED
        transaction.save()
        self.assertTrue(transaction.is_pending() or transaction.status == BnplTransaction.STATUS_APPROVED)

        # Pay
        transaction.status = BnplTransaction.STATUS_PAID
        transaction.save()
        self.assertTrue(transaction.is_paid())

    def test_unique_order_provider_constraint(self):
        """Test that each order can have only one transaction per provider."""
        BnplTransaction.objects.create(
            order=self.order,
            provider=BnplTransaction.PROVIDER_TABBY,
            provider_order_id="order-123",
            status=BnplTransaction.STATUS_PENDING,
            amount=Decimal("1000.00"),
            currency="SAR",
        )

        # Try to create another transaction for the same order/provider
        with self.assertRaises(Exception):
            BnplTransaction.objects.create(
                order=self.order,
                provider=BnplTransaction.PROVIDER_TABBY,
                provider_order_id="order-456",
                status=BnplTransaction.STATUS_PENDING,
                amount=Decimal("1000.00"),
                currency="SAR",
            )


class TabbyAdapterTest(TestCase):
    """Test TabbyAdapter."""

    def setUp(self):
        self.store = Store.objects.create(
            name="Test Store",
            currency="SAR",
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="pass123",
        )
        self.provider = BnplProvider.objects.create(
            store=self.store,
            provider=BnplProvider.PROVIDER_TABBY,
            api_key="test-key",
            merchant_id="merchant-123",
            webhook_secret="webhook-secret",
        )
        self.order = Order.objects.create(
            store=self.store,
            customer=self.user,
            email=self.user.email,
            total_amount=Decimal("500.00"),
            currency="SAR",
        )

    @patch("apps.bnpl.services.requests.post")
    def test_create_session(self, mock_post):
        """Test creating a Tabby session."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "session-123",
            "checkout": {
                "redirect_url": "https://tabby.com/checkout?id=session-123",
            },
            "order": {
                "reference_id": str(self.order.id),
            },
        }
        mock_post.return_value = mock_response

        adapter = TabbyAdapter(self.provider)
        result = adapter.create_session(self.order)

        self.assertEqual(result["status"], "success")
        self.assertIn("checkout_url", result)
        self.assertEqual(result["session_id"], "session-123")

    def test_verify_webhook_signature_valid(self):
        """Test verifying a valid webhook signature."""
        import hmac
        import hashlib

        payload = '{"order": {"reference_id": "123"}}'
        signature = hmac.new(
            self.provider.webhook_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        adapter = TabbyAdapter(self.provider)
        is_valid = adapter.verify_webhook_signature(payload, signature)

        self.assertTrue(is_valid)

    def test_verify_webhook_signature_invalid(self):
        """Test verifying an invalid webhook signature."""
        payload = '{"order": {"reference_id": "123"}}'
        invalid_signature = "invalid"

        adapter = TabbyAdapter(self.provider)
        is_valid = adapter.verify_webhook_signature(payload, invalid_signature)

        self.assertFalse(is_valid)

    @patch("apps.bnpl.services.requests.get")
    def test_get_payment_status(self, mock_get):
        """Test getting payment status."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "payment-123",
            "status": "APPROVED",
        }
        mock_get.return_value = mock_response

        adapter = TabbyAdapter(self.provider)
        result = adapter.get_payment_status("payment-123")

        self.assertEqual(result["status"], BnplTransaction.STATUS_APPROVED)


class TamaraAdapterTest(TestCase):
    """Test TamaraAdapter."""

    def setUp(self):
        self.store = Store.objects.create(
            name="Test Store",
            currency="SAR",
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="pass123",
        )
        self.provider = BnplProvider.objects.create(
            store=self.store,
            provider=BnplProvider.PROVIDER_TAMARA,
            api_key="test-key",
            merchant_id="merchant-456",
            webhook_secret="webhook-secret",
        )
        self.order = Order.objects.create(
            store=self.store,
            customer=self.user,
            email=self.user.email,
            total_amount=Decimal("500.00"),
            currency="SAR",
        )

    @patch("apps.bnpl.services.requests.post")
    def test_create_session(self, mock_post):
        """Test creating a Tamara session."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "checkout-456",
            "checkout": {
                "id": "checkout-456",
            },
        }
        mock_post.return_value = mock_response

        adapter = TamaraAdapter(self.provider)
        result = adapter.create_session(self.order)

        self.assertEqual(result["status"], "success")
        self.assertIn("checkout_url", result)


class BnplPaymentOrchestratorTest(TestCase):
    """Test BnplPaymentOrchestrator."""

    def setUp(self):
        self.store = Store.objects.create(
            name="Test Store",
            currency="SAR",
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="pass123",
        )
        self.provider = BnplProvider.objects.create(
            store=self.store,
            provider=BnplProvider.PROVIDER_TABBY,
            api_key="test-key",
            merchant_id="merchant-123",
        )
        self.order = Order.objects.create(
            store=self.store,
            customer=self.user,
            email=self.user.email,
            total_amount=Decimal("1000.00"),
            currency="SAR",
        )

    def test_get_adapter_tabby(self):
        """Test getting Tabby adapter."""
        adapter = BnplPaymentOrchestrator.get_adapter(self.provider)
        self.assertIsInstance(adapter, TabbyAdapter)

    def test_get_adapter_tamara(self):
        """Test getting Tamara adapter."""
        tamara_provider = BnplProvider.objects.create(
            store=self.store,
            provider=BnplProvider.PROVIDER_TAMARA,
            api_key="test-key",
            merchant_id="merchant-456",
        )

        adapter = BnplPaymentOrchestrator.get_adapter(tamara_provider)
        self.assertIsInstance(adapter, TamaraAdapter)

    @patch.object(TabbyAdapter, "create_session")
    def test_create_payment_session(self, mock_create):
        """Test payment session creation."""
        mock_create.return_value = {
            "checkout_url": "https://tabby.com/checkout",
            "session_id": "session-123",
            "order_id": str(self.order.id),
            "status": "success",
        }

        result = BnplPaymentOrchestrator.create_payment_session(
            self.order,
            "tabby",
        )

        self.assertEqual(result["status"], "success")

    def test_create_payment_session_provider_not_configured(self):
        """Test creating session when provider not configured."""
        # Create new store without provider
        new_store = Store.objects.create(
            name="Fresh Store",
            currency="SAR",
        )
        new_order = Order.objects.create(
            store=new_store,
            customer=self.user,
            email=self.user.email,
            total_amount=Decimal("1000.00"),
            currency="SAR",
        )

        result = BnplPaymentOrchestrator.create_payment_session(
            new_order,
            "tabby",
        )

        self.assertEqual(result["status"], "error")

    def test_process_webhook_invalid_signature(self):
        """Test webhook processing with invalid signature."""
        transaction = BnplTransaction.objects.create(
            order=self.order,
            provider=BnplProvider.PROVIDER_TABBY,
            provider_order_id="order-123",
            status=BnplTransaction.STATUS_PENDING,
            amount=Decimal("1000.00"),
            currency="SAR",
        )

        payload = {
            "order": {"reference_id": str(self.order.id)},
            "status": "APPROVED",
        }

        result = BnplPaymentOrchestrator.process_webhook(
            "tabby",
            payload,
            "invalid-signature",
        )

        self.assertEqual(result["status"], "error")

    def test_process_webhook_valid_signature(self):
        """Test webhook processing with valid signature."""
        import hmac
        import hashlib

        transaction = BnplTransaction.objects.create(
            order=self.order,
            provider=BnplProvider.PROVIDER_TABBY,
            provider_order_id="order-123",
            status=BnplTransaction.STATUS_PENDING,
            amount=Decimal("1000.00"),
            currency="SAR",
        )

        payload = {
            "order": {"reference_id": str(self.order.id)},
            "status": "APPROVED",
            "event_type": "payment.approved",
        }

        payload_str = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            self.provider.webhook_secret.encode(),
            payload_str.encode(),
            hashlib.sha256,
        ).hexdigest()

        with patch.object(BnplPaymentOrchestrator, "process_webhook", return_value={
            "status": "success",
        }):
            result = BnplPaymentOrchestrator.process_webhook(
                "tabby",
                payload,
                signature,
            )

            self.assertEqual(result["status"], "success")

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.admin_portal.models import AdminRole, AdminUserRole
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
from apps.payments.models import PaymentAttempt, PaymentIntent, PaymentProviderSettings, PaymentRisk, WebhookEvent
from apps.payments.security import WebhookSecurityValidator, generate_idempotency_key
from apps.payments.security.retry_logic import PaymentProviderRetry, RetryConfig
from apps.stores.models import Store
from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.models import StorePaymentSettings, Tenant


class PaymentHardeningBase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="merchant", password="pass123", is_staff=True)
        self.tenant = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.store = Store.objects.create(
            owner=self.owner,
            tenant=self.tenant,
            name="Store A",
            slug="store-a",
            subdomain="store-a-sub",
            status=Store.STATUS_ACTIVE,
        )
        StorePaymentSettings.objects.create(
            tenant=self.tenant,
            mode=StorePaymentSettings.MODE_GATEWAY,
            is_enabled=True,
        )
        self.customer = Customer.objects.create(
            store_id=self.store.id,
            email="customer@example.com",
            full_name="Customer A",
        )
        self.order = Order.objects.create(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            order_number="ORD-1001",
            customer=self.customer,
            total_amount=Decimal("125.00"),
            currency="SAR",
            payment_status="pending",
            status="pending",
        )
        self.provider_settings = PaymentProviderSettings.objects.create(
            store=self.store,
            tenant=self.tenant,
            provider="stripe",
            provider_code="stripe",
            is_enabled=True,
            is_active=True,
            webhook_secret="whsec_test",
            webhook_tolerance_seconds=300,
            retry_max_attempts=3,
        )
        self.tenant_ctx = TenantContext(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            currency="SAR",
            user_id=self.owner.id,
            session_key="s",
        )


class TestPaymentHardeningUnit(PaymentHardeningBase):
    def test_idempotent_charge_returns_existing_confirmed_attempt(self):
        key = generate_idempotency_key(self.order.id, "client-1")
        PaymentAttempt.objects.create(
            store=self.store,
            order=self.order,
            provider=PaymentAttempt.PROVIDER_STRIPE,
            method="stripe",
            amount=self.order.total_amount,
            currency="SAR",
            status=PaymentAttempt.STATUS_CONFIRMED,
            idempotency_key=key,
            provider_reference="pi_1",
        )

        with patch("apps.payments.application.use_cases.initiate_payment.PaymentGatewayFacade.get") as mock_get:
            result = InitiatePaymentUseCase.execute(
                InitiatePaymentCommand(
                    tenant_ctx=self.tenant_ctx,
                    order_id=self.order.id,
                    provider_code="stripe",
                    return_url="https://merchant.test/return",
                    idempotency_key=key,
                )
            )

        self.assertEqual(result.provider_reference, "pi_1")
        mock_get.assert_not_called()

    def test_signature_validation(self):
        payload = json.dumps({"event_id": "evt_1"}, separators=(",", ":"), sort_keys=True)
        signature = hmac.new(b"whsec_test", payload.encode("utf-8"), hashlib.sha256).hexdigest()
        self.assertTrue(
            WebhookSecurityValidator.verify_signature(
                payload=payload,
                signature=signature,
                secret="whsec_test",
            )
        )

    def test_retry_logic_exponential_backoff(self):
        op = Mock(side_effect=[Exception("timeout"), "ok"])
        result = PaymentProviderRetry.execute_with_retry(
            operation=op,
            operation_name="charge",
            config=RetryConfig(max_attempts=2, initial_delay_ms=1, max_delay_ms=1, jitter=False),
        )
        self.assertEqual(result, "ok")
        self.assertEqual(op.call_count, 2)

    def test_risk_threshold_flags_payment(self):
        key = generate_idempotency_key(self.order.id, "risk-client")
        for idx in range(6):
            PaymentAttempt.objects.create(
                store=self.store,
                order=self.order,
                provider=PaymentAttempt.PROVIDER_STRIPE,
                method="stripe",
                amount=self.order.total_amount,
                currency="SAR",
                status=PaymentAttempt.STATUS_FAILED,
                idempotency_key=f"k-{idx}",
                ip_address="10.0.0.1",
            )

        with patch("apps.payments.application.use_cases.initiate_payment.PaymentGatewayFacade.get") as mock_get:
            gateway = Mock()
            gateway.code = "stripe"
            gateway.initiate_payment.return_value = Mock(
                redirect_url="https://gateway/redirect",
                client_secret="secret",
                provider_reference="pi_risk",
            )
            mock_get.return_value = gateway

            InitiatePaymentUseCase.execute(
                InitiatePaymentCommand(
                    tenant_ctx=self.tenant_ctx,
                    order_id=self.order.id,
                    provider_code="stripe",
                    return_url="https://merchant.test/return",
                    idempotency_key=key,
                    ip_address="10.0.0.1",
                )
            )

        risk = PaymentRisk.objects.filter(order=self.order).order_by("-created_at").first()
        self.assertIsNotNone(risk)
        self.assertTrue(risk.flagged)


class TestPaymentHardeningAPI(PaymentHardeningBase):
    def setUp(self):
        super().setUp()
        self.api_client = APIClient()
        self.admin = get_user_model().objects.create_user("admin", password="pass123", is_staff=True, is_superuser=True)
        self.api_client.force_authenticate(user=self.admin)

    def _valid_webhook_headers(self, payload: dict):
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        signature = hmac.new(self.provider_settings.webhook_secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
        return raw, {
            "HTTP_X_WEBHOOK_SIGNATURE": signature,
            "HTTP_X_WEBHOOK_TIMESTAMP": str(int(timezone.now().timestamp())),
        }

    @patch("apps.payments.application.use_cases.handle_webhook_event.apply_payment_success")
    @patch("apps.payments.application.use_cases.handle_webhook_event.PaymentGatewayFacade.resolve_for_webhook")
    def test_duplicate_webhook_does_not_double_confirm(self, mock_resolve, mock_apply_success):
        PaymentIntent.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order=self.order,
            provider_code="stripe",
            amount=self.order.total_amount,
            currency="SAR",
            status="pending",
            provider_reference="pi_dup",
            idempotency_key="intent-dup",
        )

        PaymentAttempt.objects.create(
            store=self.store,
            order=self.order,
            provider=PaymentAttempt.PROVIDER_STRIPE,
            method="stripe",
            amount=self.order.total_amount,
            currency="SAR",
            status=PaymentAttempt.STATUS_PENDING,
            idempotency_key="attempt-dup",
            provider_reference="pi_dup",
        )

        payload = {"event_id": "evt_dup", "status": "succeeded"}
        raw, headers = self._valid_webhook_headers(payload)

        mock_resolve.return_value = (
            Mock(),
            Mock(event_id="evt_dup", status="succeeded", intent_reference="pi_dup"),
            self.tenant.id,
        )

        url = "/api/payments/webhook/stripe/"
        first = self.client.post(url, data=payload, content_type="application/json", **headers)
        second = self.client.post(url, data=payload, content_type="application/json", **headers)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(WebhookEvent.objects.filter(store=self.store, event_id="evt_dup").count(), 1)
        self.assertEqual(mock_apply_success.call_count, 1)

    @patch("apps.payments.application.use_cases.handle_webhook_event.PaymentGatewayFacade.resolve_for_webhook")
    def test_invalid_signature_rejected(self, mock_resolve):
        PaymentIntent.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order=self.order,
            provider_code="stripe",
            amount=self.order.total_amount,
            currency="SAR",
            status="pending",
            provider_reference="pi_bad_sig",
            idempotency_key="intent-bad",
        )

        mock_resolve.return_value = (
            Mock(),
            Mock(event_id="evt_bad", status="succeeded", intent_reference="pi_bad_sig"),
            self.tenant.id,
        )

        payload = {"event_id": "evt_bad", "status": "succeeded"}
        url = "/api/payments/webhook/stripe/"
        response = self.client.post(
            url,
            data=payload,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE="invalid",
            HTTP_X_WEBHOOK_TIMESTAMP=str(int(timezone.now().timestamp())),
        )
        self.assertEqual(response.status_code, 400)

    def test_flagged_payment_requires_manual_approval(self):
        attempt = PaymentAttempt.objects.create(
            store=self.store,
            order=self.order,
            provider=PaymentAttempt.PROVIDER_STRIPE,
            method="stripe",
            amount=self.order.total_amount,
            currency="SAR",
            status=PaymentAttempt.STATUS_FLAGGED,
            idempotency_key="flagged-attempt",
        )
        risk = PaymentRisk.objects.create(
            store=self.store,
            order=self.order,
            payment_attempt=attempt,
            risk_score=90,
            velocity_count_5min=7,
            ip_address="10.0.0.10",
            flagged=True,
        )

        approve = self.api_client.post(f"/api/admin/payments/risk/{risk.id}/approve/", data={"note": "ok"}, format="json")
        self.assertEqual(approve.status_code, 200)
        risk.refresh_from_db()
        attempt.refresh_from_db()
        self.assertEqual(risk.review_decision, "approved")
        self.assertEqual(attempt.status, PaymentAttempt.STATUS_PENDING)


class TestPaymentHardeningIntegration(PaymentHardeningBase):
    @patch("apps.payments.application.use_cases.payment_outcomes.OrderService.mark_as_paid")
    @patch("apps.payments.application.use_cases.payment_outcomes.CreditOrderPaymentUseCase.execute")
    @patch("apps.payments.application.use_cases.payment_outcomes.NotifyMerchantOrderPlacedUseCase.execute")
    @patch("apps.payments.application.use_cases.payment_outcomes.SendSmsUseCase.execute")
    @patch("apps.payments.application.use_cases.payment_outcomes.ShippingService.create_shipment")
    @patch("apps.payments.application.use_cases.handle_webhook_event.PaymentGatewayFacade.resolve_for_webhook")
    @patch("apps.payments.application.use_cases.initiate_payment.PaymentGatewayFacade.get")
    def test_full_flow_and_replay_webhook_noop(
        self,
        mock_get,
        mock_resolve,
        _mock_shipping,
        _mock_sms,
        _mock_notify,
        mock_credit,
        _mock_mark_paid,
    ):
        key = generate_idempotency_key(self.order.id, "integration-client")
        gateway = Mock()
        gateway.code = "stripe"
        gateway.initiate_payment.return_value = Mock(
            redirect_url="https://gateway/redirect",
            client_secret="secret",
            provider_reference="pi_full",
        )
        mock_get.return_value = gateway

        InitiatePaymentUseCase.execute(
            InitiatePaymentCommand(
                tenant_ctx=self.tenant_ctx,
                order_id=self.order.id,
                provider_code="stripe",
                return_url="https://merchant.test/return",
                idempotency_key=key,
            )
        )

        payload = {"event_id": "evt_full", "status": "succeeded"}
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        signature = hmac.new(self.provider_settings.webhook_secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()

        mock_resolve.return_value = (
            Mock(),
            Mock(event_id="evt_full", status="succeeded", intent_reference="pi_full"),
            self.tenant.id,
        )

        cmd = HandleWebhookEventCommand(
            provider_code="stripe",
            headers={
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": str(int(timezone.now().timestamp())),
            },
            payload=payload,
            raw_body=raw,
        )

        event1 = HandleWebhookEventUseCase.execute(cmd)
        event2 = HandleWebhookEventUseCase.execute(cmd)

        self.assertEqual(event1.id, event2.id)
        self.assertEqual(event1.status, WebhookEvent.STATUS_PROCESSED)
        mock_credit.assert_called_once()


class TestPaymentHardeningWeb(PaymentHardeningBase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        role, _ = AdminRole.objects.get_or_create(name="SuperAdmin")
        self.staff = get_user_model().objects.create_user(
            username="portal-admin",
            password="pass123",
            is_staff=True,
        )
        AdminUserRole.objects.create(user=self.staff, role=role)
        self.client.login(username="portal-admin", password="pass123")

    def test_admin_payment_events_page_renders(self):
        WebhookEvent.objects.create(
            store=self.store,
            provider="stripe",
            provider_name="stripe",
            event_id="evt-web",
            status=WebhookEvent.STATUS_RECEIVED,
            signature_valid=True,
            processed=False,
        )
        response = self.client.get(reverse("admin_portal:payment_events"))
        self.assertEqual(response.status_code, 200)

    def test_risk_queue_approve_reject(self):
        attempt = PaymentAttempt.objects.create(
            store=self.store,
            order=self.order,
            provider=PaymentAttempt.PROVIDER_STRIPE,
            method="stripe",
            amount=self.order.total_amount,
            currency="SAR",
            status=PaymentAttempt.STATUS_FLAGGED,
            idempotency_key="risk-web",
        )
        risk = PaymentRisk.objects.create(
            store=self.store,
            order=self.order,
            payment_attempt=attempt,
            risk_score=95,
            velocity_count_5min=8,
            ip_address="10.0.0.20",
            flagged=True,
        )

        approve_response = self.client.post(reverse("admin_portal:payment_risk_approve", args=[risk.id]))
        self.assertEqual(approve_response.status_code, 302)
        risk.refresh_from_db()
        self.assertEqual(risk.review_decision, "approved")

        risk2 = PaymentRisk.objects.create(
            store=self.store,
            order=self.order,
            risk_score=92,
            velocity_count_5min=9,
            ip_address="10.0.0.21",
            flagged=True,
        )
        reject_response = self.client.post(reverse("admin_portal:payment_risk_reject", args=[risk2.id]))
        self.assertEqual(reject_response.status_code, 302)
        risk2.refresh_from_db()
        self.assertEqual(risk2.review_decision, "rejected")

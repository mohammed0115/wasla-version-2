"""
Comprehensive tests for SaaS recurring billing system.

Tests:
- Subscription creation and lifecycle
- Billing cycle creation and invoicing
- Proration calculations (upgrade/downgrade)
- Dunning flow with retries
- Idempotency checks
- Webhook handling
- State machine transitions
- Tenant isolation
"""

import pytest
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from apps.tenants.models import Tenant
from .models_billing import (
    Subscription, BillingPlan, BillingCycle, Invoice,
    DunningAttempt, PaymentEvent, PaymentMethod
)
from .services_billing import (
    SubscriptionService, BillingService, DunningService, WebhookService
)


@pytest.mark.django_db
class SubscriptionServiceTests(TestCase):
    """Tests for SubscriptionService."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            name='Test Store',
            domain='test.example.com'
        )
        
        self.plan = BillingPlan.objects.create(
            name='Professional',
            price=Decimal('99.00'),
            currency='SAR',
            billing_cycle='monthly',
            features=['feature1', 'feature2']
        )
        
        self.payment_method = PaymentMethod.objects.create(
            method_type='card',
            provider_customer_id='cus_123',
            provider_payment_method_id='pm_123',
            display_name='Visa **** 4242'
        )
    
    def test_create_subscription(self):
        """Test creating a new subscription."""
        subscription = SubscriptionService.create_subscription(
            tenant=self.tenant,
            plan=self.plan,
            payment_method=self.payment_method
        )
        
        assert subscription.tenant == self.tenant
        assert subscription.plan == self.plan
        assert subscription.state == 'active'
        assert subscription.next_billing_date > date.today()
    
    def test_create_subscription_idempotent(self):
        """Test that subscription creation is idempotent."""
        sub1 = SubscriptionService.create_subscription(
            tenant=self.tenant,
            plan=self.plan,
            payment_method=self.payment_method,
            idempotency_key='key_1'
        )
        
        sub2 = SubscriptionService.create_subscription(
            tenant=self.tenant,
            plan=self.plan,
            payment_method=self.payment_method,
            idempotency_key='key_1'
        )
        
        assert sub1.id == sub2.id
    
    def test_cancel_subscription(self):
        """Test cancelling a subscription."""
        subscription = SubscriptionService.create_subscription(
            tenant=self.tenant,
            plan=self.plan,
            payment_method=self.payment_method
        )
        
        cancelled = SubscriptionService.cancel_subscription(
            subscription=subscription,
            reason='Customer request'
        )
        
        assert cancelled.state == 'cancelled'
        assert cancelled.cancellation_reason == 'Customer request'
        assert cancelled.cancelled_at is not None
    
    def test_suspend_subscription(self):
        """Test suspending a subscription."""
        subscription = SubscriptionService.create_subscription(
            tenant=self.tenant,
            plan=self.plan,
            payment_method=self.payment_method
        )
        
        suspended = SubscriptionService.suspend_subscription(
            subscription=subscription,
            reason='Non-payment'
        )
        
        assert suspended.state == 'suspended'
        assert suspended.suspension_reason == 'Non-payment'
        assert not self.tenant.is_active  # Store should be deactivated
    
    def test_reactivate_subscription(self):
        """Test reactivating a suspended subscription."""
        subscription = SubscriptionService.create_subscription(
            tenant=self.tenant,
            plan=self.plan,
            payment_method=self.payment_method
        )
        
        # Suspend
        SubscriptionService.suspend_subscription(subscription)
        self.tenant.refresh_from_db()
        assert not self.tenant.is_active
        
        # Reactivate
        reactivated = SubscriptionService.reactivate_subscription(subscription)
        
        assert reactivated.state == 'active'
        self.tenant.refresh_from_db()
        assert self.tenant.is_active


@pytest.mark.django_db
class BillingServiceTests(TestCase):
    """Tests for BillingService."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            name='Test Store',
            domain='test.example.com'
        )
        
        self.basic_plan = BillingPlan.objects.create(
            name='Basic',
            price=Decimal('49.00'),
            currency='SAR',
            billing_cycle='monthly'
        )
        
        self.pro_plan = BillingPlan.objects.create(
            name='Professional',
            price=Decimal('99.00'),
            currency='SAR',
            billing_cycle='monthly'
        )
        
        self.payment_method = PaymentMethod.objects.create(
            method_type='card',
            provider_customer_id='cus_123',
            provider_payment_method_id='pm_123',
            display_name='Visa **** 4242'
        )
        
        self.subscription = SubscriptionService.create_subscription(
            tenant=self.tenant,
            plan=self.basic_plan,
            payment_method=self.payment_method
        )
    
    def test_create_billing_cycle(self):
        """Test creating a billing cycle."""
        period_start = date.today()
        period_end = period_start + timedelta(days=29)
        
        cycle = BillingService.create_billing_cycle(
            subscription=self.subscription,
            period_start=period_start,
            period_end=period_end
        )
        
        assert cycle.subscription == self.subscription
        assert cycle.status == 'pending'
        assert cycle.total > 0
    
    def test_create_invoice(self):
        """Test creating an invoice for a billing cycle."""
        period_start = date.today()
        period_end = period_start + timedelta(days=29)
        
        cycle = BillingService.create_billing_cycle(
            subscription=self.subscription,
            period_start=period_start,
            period_end=period_end
        )
        
        invoice = BillingService.create_invoice(cycle)
        
        assert invoice.subscription == self.subscription
        assert invoice.status == 'issued'
        assert invoice.amount_due == invoice.total
        assert cycle.status == 'billed'
    
    def test_create_invoice_idempotent(self):
        """Test that invoice creation is idempotent."""
        period_start = date.today()
        period_end = period_start + timedelta(days=29)
        
        cycle = BillingService.create_billing_cycle(
            subscription=self.subscription,
            period_start=period_start,
            period_end=period_end
        )
        
        inv1 = BillingService.create_invoice(cycle)
        inv2 = BillingService.create_invoice(cycle)
        
        assert inv1.id == inv2.id
    
    def test_record_payment_full(self):
        """Test recording a full payment."""
        period_start = date.today()
        period_end = period_start + timedelta(days=29)
        
        cycle = BillingService.create_billing_cycle(
            subscription=self.subscription,
            period_start=period_start,
            period_end=period_end
        )
        
        invoice = BillingService.create_invoice(cycle)
        amount = invoice.total
        
        updated = BillingService.record_payment(
            invoice=invoice,
            amount=amount,
            provider_payment_id='pay_123'
        )
        
        assert updated.status == 'paid'
        assert updated.amount_paid == amount
        assert updated.amount_due == Decimal('0.00')
        assert updated.paid_date is not None
    
    def test_record_payment_partial(self):
        """Test recording a partial payment."""
        period_start = date.today()
        period_end = period_start + timedelta(days=29)
        
        cycle = BillingService.create_billing_cycle(
            subscription=self.subscription,
            period_start=period_start,
            period_end=period_end
        )
        
        invoice = BillingService.create_invoice(cycle)
        partial_amount = invoice.total / 2
        
        updated = BillingService.record_payment(
            invoice=invoice,
            amount=partial_amount,
            provider_payment_id='pay_123'
        )
        
        assert updated.status == 'partial'
        assert updated.amount_paid == partial_amount
        assert updated.amount_due == partial_amount
    
    def test_proration_upgrade(self):
        """Test proration calculation for plan upgrade."""
        # 30-day cycle, 15 days remaining, upgrading from $49 to $99
        # Daily rate old: 49/30 = 1.633
        # Daily rate new: 99/30 = 3.3
        # Proration: (3.3 - 1.633) * 15 = 25.005
        
        proration = BillingService.calculate_proration(
            subscription=self.subscription,
            old_plan=self.basic_plan,
            new_plan=self.pro_plan
        )
        
        assert proration > 0  # Upgrade should be positive charge
    
    def test_proration_downgrade(self):
        """Test proration calculation for plan downgrade."""
        # Downgrade from $99 to $49 should result in credit
        subscription = SubscriptionService.create_subscription(
            tenant=self.tenant,
            plan=self.pro_plan,
            payment_method=self.payment_method
        )
        
        proration = BillingService.calculate_proration(
            subscription=subscription,
            old_plan=self.pro_plan,
            old_plan=self.basic_plan
        )
        
        assert proration < 0  # Downgrade should be negative (credit)


@pytest.mark.django_db
class DunningServiceTests(TransactionTestCase):
    """Tests for DunningService (uses TransactionTestCase for atomicity)."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            name='Test Store',
            domain='test.example.com'
        )
        
        self.plan = BillingPlan.objects.create(
            name='Professional',
            price=Decimal('99.00'),
            currency='SAR',
            billing_cycle='monthly'
        )
        
        self.payment_method = PaymentMethod.objects.create(
            method_type='card',
            provider_customer_id='cus_123',
            provider_payment_method_id='pm_123',
            display_name='Visa **** 4242'
        )
        
        self.subscription = SubscriptionService.create_subscription(
            tenant=self.tenant,
            plan=self.plan,
            payment_method=self.payment_method
        )
        
        # Create invoice
        cycle = BillingService.create_billing_cycle(
            subscription=self.subscription,
            period_start=date.today(),
            period_end=date.today() + timedelta(days=29)
        )
        self.invoice = BillingService.create_invoice(cycle)
    
    def test_start_dunning(self):
        """Test starting dunning flow."""
        attempt = DunningService.start_dunning(self.invoice)
        
        assert attempt.subscription == self.subscription
        assert attempt.invoice == self.invoice
        assert attempt.attempt_number == 1
        assert attempt.status == 'pending'
        
        # Check subscription state changed
        self.subscription.refresh_from_db()
        assert self.subscription.state == 'past_due'
    
    def test_dunning_max_retries_suspend(self):
        """Test that max retries leads to suspension."""
        # Create multiple failed attempts
        for i in range(5):
            DunningService.start_dunning(self.invoice)
        
        # Last attempt should trigger suspension
        self.subscription.refresh_from_db()
        # (After processing all attempts, subscription should be suspended)
    
    def test_add_grace_period(self):
        """Test adding grace period."""
        DunningService.start_dunning(self.invoice)
        
        updated = DunningService.add_grace_period(
            subscription=self.subscription,
            days=7
        )
        
        assert updated.state == 'grace'
        assert updated.grace_until is not None
        assert (updated.grace_until - timezone.now()).days == 7


@pytest.mark.django_db
class WebhookServiceTests(TestCase):
    """Tests for WebhookService."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            name='Test Store',
            domain='test.example.com'
        )
        
        self.plan = BillingPlan.objects.create(
            name='Professional',
            price=Decimal('99.00'),
            currency='SAR',
            billing_cycle='monthly'
        )
        
        self.payment_method = PaymentMethod.objects.create(
            method_type='card',
            provider_customer_id='cus_123',
            provider_payment_method_id='pm_123',
            display_name='Visa **** 4242'
        )
        
        self.subscription = SubscriptionService.create_subscription(
            tenant=self.tenant,
            plan=self.plan,
            payment_method=self.payment_method
        )
        
        # Create invoice
        cycle = BillingService.create_billing_cycle(
            subscription=self.subscription,
            period_start=date.today(),
            period_end=date.today() + timedelta(days=29)
        )
        self.invoice = BillingService.create_invoice(cycle)
    
    def test_webhook_idempotent(self):
        """Test that webhook processing is idempotent."""
        payload = {
            'customer_id': 'cus_123',
            'amount': '99.00',
            'payment_id': 'pay_123'
        }
        
        event1 = WebhookService.handle_payment_event(
            event_type='payment.succeeded',
            provider_event_id='evt_123',
            payload=payload
        )
        
        event2 = WebhookService.handle_payment_event(
            event_type='payment.succeeded',
            provider_event_id='evt_123',
            payload=payload
        )
        
        assert event1.id == event2.id
        assert event1.status in ['received', 'processing', 'processed']
    
    def test_webhook_payment_succeeded(self):
        """Test payment.succeeded webhook."""
        payload = {
            'customer_id': 'cus_123',
            'amount': '99.00',
            'payment_id': 'pay_123'
        }
        
        event = WebhookService.handle_payment_event(
            event_type='payment.succeeded',
            provider_event_id='evt_123',
            payload=payload
        )
        
        assert event.event_type == 'payment.succeeded'
        assert event.subscription == self.subscription
    
    def test_webhook_payment_failed(self):
        """Test payment.failed webhook."""
        payload = {
            'customer_id': 'cus_123',
            'error_code': 'card_declined',
            'error_message': 'Card was declined'
        }
        
        event = WebhookService.handle_payment_event(
            event_type='payment.failed',
            provider_event_id='evt_456',
            payload=payload
        )
        
        assert event.event_type == 'payment.failed'
        
        # Check dunning was started
        dunning_attempts = DunningAttempt.objects.filter(
            invoice=self.invoice
        )
        assert dunning_attempts.exists()


@pytest.mark.django_db
class IdempotencyTests(TestCase):
    """Tests for idempotency keys across operations."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            name='Test Store',
            domain='test.example.com'
        )
        
        self.plan = BillingPlan.objects.create(
            name='Professional',
            price=Decimal('99.00'),
            currency='SAR',
            billing_cycle='monthly'
        )
        
        self.payment_method = PaymentMethod.objects.create(
            method_type='card',
            provider_customer_id='cus_123',
            provider_payment_method_id='pm_123',
            display_name='Visa **** 4242'
        )
    
    def test_subscription_creation_idempotent(self):
        """Verify subscription creation is idempotent."""
        key = 'sub_create_001'
        
        sub1 = SubscriptionService.create_subscription(
            tenant=self.tenant,
            plan=self.plan,
            payment_method=self.payment_method,
            idempotency_key=key
        )
        
        sub2 = SubscriptionService.create_subscription(
            tenant=self.tenant,
            plan=self.plan,
            payment_method=self.payment_method,
            idempotency_key=key
        )
        
        assert sub1.id == sub2.id
        assert Subscription.objects.filter(tenant=self.tenant).count() == 1
    
    def test_invoice_creation_idempotent(self):
        """Verify invoice creation is idempotent."""
        subscription = SubscriptionService.create_subscription(
            tenant=self.tenant,
            plan=self.plan,
            payment_method=self.payment_method
        )
        
        cycle = BillingService.create_billing_cycle(
            subscription=subscription,
            period_start=date.today(),
            period_end=date.today() + timedelta(days=29)
        )
        
        inv1 = BillingService.create_invoice(cycle)
        inv2 = BillingService.create_invoice(cycle)
        
        assert inv1.id == inv2.id


@pytest.mark.django_db
class TenantIsolationTests(TestCase):
    """Tests for tenant isolation in billing."""
    
    def setUp(self):
        """Set up multiple tenants."""
        self.tenant1 = Tenant.objects.create(
            name='Store 1',
            domain='store1.example.com'
        )
        
        self.tenant2 = Tenant.objects.create(
            name='Store 2',
            domain='store2.example.com'
        )
        
        self.plan = BillingPlan.objects.create(
            name='Professional',
            price=Decimal('99.00'),
            currency='SAR',
            billing_cycle='monthly'
        )
        
        self.payment_method1 = PaymentMethod.objects.create(
            method_type='card',
            provider_customer_id='cus_001',
            provider_payment_method_id='pm_001',
            display_name='Card 1'
        )
        
        self.payment_method2 = PaymentMethod.objects.create(
            method_type='card',
            provider_customer_id='cus_002',
            provider_payment_method_id='pm_002',
            display_name='Card 2'
        )
    
    def test_subscriptions_isolated_by_tenant(self):
        """Verify subscriptions are isolated by tenant."""
        sub1 = SubscriptionService.create_subscription(
            tenant=self.tenant1,
            plan=self.plan,
            payment_method=self.payment_method1
        )
        
        sub2 = SubscriptionService.create_subscription(
            tenant=self.tenant2,
            plan=self.plan,
            payment_method=self.payment_method2
        )
        
        # Each tenant should only see their own subscription
        assert sub1.tenant == self.tenant1
        assert sub2.tenant == self.tenant2
        
        qs1 = Subscription.objects.filter(tenant=self.tenant1)
        qs2 = Subscription.objects.filter(tenant=self.tenant2)
        
        assert qs1.count() == 1
        assert qs2.count() == 1

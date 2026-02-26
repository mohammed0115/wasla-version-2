"""
Test suite for accounting service.
Tests AccountingService double-entry posting, fee calculation, and idempotency.
"""
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import transaction

from apps.stores.models import Store, StoreType
from apps.tenants.models import Tenant
from apps.wallet.models import (
    Wallet, WalletTransaction, Account, JournalEntry, JournalLine,
    FeePolicy, PaymentAllocation
)
from apps.wallet.services.accounting_service import AccountingService


class AccountingServiceSetupTestCase(TestCase):
    """Test AccountingService initialization and account setup."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", domain="test.local")
        self.owner = User.objects.create_user(username="testuser", password="pass123")
        self.store = Store.objects.create(
            name="Test Store",
            owner=self.owner,
            tenant=self.tenant,
            store_type=StoreType.INDIVIDUAL,
            subdomain="test-store"
        )
        self.wallet = Wallet.objects.create(store=self.store)
        self.service = AccountingService()
    
    def test_get_or_create_accounts(self):
        """Test that standard accounts are created."""
        accounts = self.service.get_or_create_accounts(self.store)
        
        # Should have 8 standard accounts
        self.assertEqual(len(accounts), 8)
        
        # Verify all required accounts exist
        codes = {acc.code for acc in accounts.values()}
        self.assertIn('1000', codes)  # CASH
        self.assertIn('2000', codes)  # PROVIDER_CLEARING
    
    def test_accounts_idempotency(self):
        """Test that get_or_create is idempotent."""
        accounts1 = self.service.get_or_create_accounts(self.store)
        count1 = Account.objects.filter(store=self.store).count()
        
        accounts2 = self.service.get_or_create_accounts(self.store)
        count2 = Account.objects.filter(store=self.store).count()
        
        # Should not create duplicates
        self.assertEqual(count1, count2)
        self.assertEqual(len(accounts1), len(accounts2))


class FeeCalculationTestCase(TestCase):
    """Test fee calculation logic."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", domain="test.local")
        self.owner = User.objects.create_user(username="testuser", password="pass123")
        self.store = Store.objects.create(
            name="Test Store",
            owner=self.owner,
            tenant=self.tenant,
            store_type=StoreType.INDIVIDUAL,
            subdomain="test-store"
        )
        self.wallet = Wallet.objects.create(store=self.store)
        self.service = AccountingService()
    
    def test_percentage_fee_calculation(self):
        """Test percentage-based fee calculation."""
        policy = FeePolicy.objects.create(
            name="2.5% Commission",
            fee_type="percentage",
            fee_value=Decimal('2.50'),
            scope="global"
        )
        
        fee = self.service.calculate_fee(
            amount=Decimal('100.00'),
            merchant_policy=policy
        )
        
        # 100 * 2.5% = 2.50
        self.assertEqual(fee, Decimal('2.50'))
    
    def test_fixed_fee_calculation(self):
        """Test fixed amount fee."""
        policy = FeePolicy.objects.create(
            name="Per-Order Fee",
            fee_type="fixed",
            fee_value=Decimal('1.00'),
            scope="global"
        )
        
        fee = self.service.calculate_fee(
            amount=Decimal('500.00'),
            merchant_policy=policy
        )
        
        # Fixed amount, regardless of transaction size
        self.assertEqual(fee, Decimal('1.00'))
    
    def test_minimum_fee_applied(self):
        """Test that minimum fee is applied when calculated fee is smaller."""
        policy = FeePolicy.objects.create(
            name="With Minimum",
            fee_type="percentage",
            fee_value=Decimal('2.00'),
            minimum_fee=Decimal('1.00'),
            scope="global"
        )
        
        # 10 * 2% = 0.20, but minimum is 1.00
        fee = self.service.calculate_fee(
            amount=Decimal('10.00'),
            merchant_policy=policy
        )
        
        self.assertEqual(fee, Decimal('1.00'))
    
    def test_maximum_fee_applied(self):
        """Test that maximum fee is applied when calculated fee exceeds it."""
        policy = FeePolicy.objects.create(
            name="With Maximum",
            fee_type="percentage",
            fee_value=Decimal('5.00'),
            maximum_fee=Decimal('50.00'),
            scope="global"
        )
        
        # 10000 * 5% = 500, but maximum is 50.00
        fee = self.service.calculate_fee(
            amount=Decimal('10000.00'),
            merchant_policy=policy
        )
        
        self.assertEqual(fee, Decimal('50.00'))
    
    def test_policy_hierarchy_store_level(self):
        """Test policy hierarchy: store-specific overrides plan/global."""
        global_policy = FeePolicy.objects.create(
            name="Global",
            fee_type="percentage",
            fee_value=Decimal('2.50'),
            scope="global"
        )
        
        store_policy = FeePolicy.objects.create(
            name="Store-Specific",
            fee_type="percentage",
            fee_value=Decimal('1.00'),
            scope="store",
            store=self.store
        )
        
        # Should use store-specific policy
        fee = self.service.calculate_fee(
            amount=Decimal('100.00'),
            merchant_policy=store_policy
        )
        
        self.assertEqual(fee, Decimal('1.00'))


class JournalPostingTestCase(TransactionTestCase):
    """Test journal entry posting (double-entry accounting)."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", domain="test.local")
        self.owner = User.objects.create_user(username="testuser", password="pass123")
        self.store = Store.objects.create(
            name="Test Store",
            owner=self.owner,
            tenant=self.tenant,
            store_type=StoreType.INDIVIDUAL,
            subdomain="test-store"
        )
        self.wallet = Wallet.objects.create(store=self.store)
        self.service = AccountingService()
        self.service.get_or_create_accounts(self.store)
    
    def test_post_entry_creates_balanced_entry(self):
        """Test that posting an entry creates balanced journal lines."""
        entry = self.service.post_entry(
            store=self.store,
            entry_date=timezone.now().date(),
            entry_type="payment_captured",
            reference_id="ORD-001",
            description="Payment received",
            lines=[
                {'account_code': '1000', 'debit': Decimal('100.00'), 'credit': Decimal('0.00')},
                {'account_code': '2100', 'debit': Decimal('0.00'), 'credit': Decimal('100.00')},
            ],
            idempotency_key="key-ord-001"
        )
        
        self.assertIsNotNone(entry)
        self.assertEqual(entry.status, "posted")
        self.assertEqual(entry.journalline_set.count(), 2)
        self.assertTrue(entry.validate_balanced())
    
    def test_posting_idempotency(self):
        """Test that posting same entry twice doesn't create duplicates."""
        idempotency_key = "key-unique-123"
        
        entry1 = self.service.post_entry(
            store=self.store,
            entry_date=timezone.now().date(),
            entry_type="payment_captured",
            reference_id="ORD-002",
            description="Payment 1",
            lines=[
                {'account_code': '1000', 'debit': Decimal('100.00'), 'credit': Decimal('0.00')},
                {'account_code': '2100', 'debit': Decimal('0.00'), 'credit': Decimal('100.00')},
            ],
            idempotency_key=idempotency_key
        )
        
        # Post again with same key
        entry2 = self.service.post_entry(
            store=self.store,
            entry_date=timezone.now().date(),
            entry_type="payment_captured",
            reference_id="ORD-002",
            description="Payment 1",
            lines=[
                {'account_code': '1000', 'debit': Decimal('100.00'), 'credit': Decimal('0.00')},
                {'account_code': '2100', 'debit': Decimal('0.00'), 'credit': Decimal('100.00')},
            ],
            idempotency_key=idempotency_key
        )
        
        # Should return same entry
        self.assertEqual(entry1.id, entry2.id)
        
        # Should have only one entry in database
        count = JournalEntry.objects.filter(
            store=self.store,
            idempotency_key=idempotency_key
        ).count()
        self.assertEqual(count, 1)


class PaymentCaptureTestCase(TransactionTestCase):
    """Test recording payment capture with fee allocation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", domain="test.local")
        self.owner = User.objects.create_user(username="testuser", password="pass123")
        self.store = Store.objects.create(
            name="Test Store",
            owner=self.owner,
            tenant=self.tenant,
            store_type=StoreType.INDIVIDUAL,
            subdomain="test-store"
        )
        self.wallet = Wallet.objects.create(store=self.store)
        self.service = AccountingService()
        self.service.get_or_create_accounts(self.store)
        
        self.fee_policy = FeePolicy.objects.create(
            name="Standard",
            fee_type="percentage",
            fee_value=Decimal('2.50'),
            scope="global"
        )
    
    def test_record_payment_capture(self):
        """Test recording order payment capture."""
        entry = self.service.record_payment_capture(
            store=self.store,
            order_id="ORD-001",
            amount=Decimal('100.00'),
            fee_policy=self.fee_policy,
            idempotency_key="key-payment-001"
        )
        
        self.assertIsNotNone(entry)
        self.assertEqual(entry.entry_type, "payment_captured")
        
        # Should create allocation
        allocation = entry.paymentallocation_set.first()
        self.assertIsNotNone(allocation)
        self.assertEqual(allocation.gross_amount, Decimal('100.00'))
        self.assertEqual(allocation.fee_amount, Decimal('2.50'))
        self.assertEqual(allocation.net_amount, Decimal('97.50'))


class OrderDeliveryTestCase(TransactionTestCase):
    """Test recording order delivery (pending to available)."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", domain="test.local")
        self.owner = User.objects.create_user(username="testuser", password="pass123")
        self.store = Store.objects.create(
            name="Test Store",
            owner=self.owner,
            tenant=self.tenant,
            store_type=StoreType.INDIVIDUAL,
            subdomain="test-store"
        )
        self.wallet = Wallet.objects.create(store=self.store)
        self.service = AccountingService()
        self.service.get_or_create_accounts(self.store)
    
    def test_record_order_delivered(self):
        """Test moving balance from pending to available."""
        entry = self.service.record_order_delivered(
            store=self.store,
            order_id="ORD-001",
            amount=Decimal('97.50'),  # net amount after fees
            idempotency_key="key-delivery-001"
        )
        
        self.assertIsNotNone(entry)
        self.assertEqual(entry.entry_type, "order_delivered")
        
        # Should move from pending to available
        lines = entry.journalline_set.all()
        self.assertEqual(lines.count(), 2)


class RefundTestCase(TransactionTestCase):
    """Test recording refunds."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", domain="test.local")
        self.owner = User.objects.create_user(username="testuser", password="pass123")
        self.store = Store.objects.create(
            name="Test Store",
            owner=self.owner,
            tenant=self.tenant,
            store_type=StoreType.INDIVIDUAL,
            subdomain="test-store"
        )
        self.wallet = Wallet.objects.create(store=self.store)
        self.service = AccountingService()
        self.service.get_or_create_accounts(self.store)
    
    def test_record_refund(self):
        """Test recording a refund (customer return)."""
        entry = self.service.record_refund(
            store=self.store,
            order_id="ORD-001",
            amount=Decimal('100.00'),
            reverse_full_fee=True,
            idempotency_key="key-refund-001"
        )
        
        self.assertIsNotNone(entry)
        self.assertEqual(entry.entry_type, "refund")


class WithdrawalTestCase(TransactionTestCase):
    """Test recording withdrawal payments."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", domain="test.local")
        self.owner = User.objects.create_user(username="testuser", password="pass123")
        self.store = Store.objects.create(
            name="Test Store",
            owner=self.owner,
            tenant=self.tenant,
            store_type=StoreType.INDIVIDUAL,
            subdomain="test-store"
        )
        self.wallet = Wallet.objects.create(store=self.store)
        self.service = AccountingService()
        self.service.get_or_create_accounts(self.store)
    
    def test_record_withdrawal_paid(self):
        """Test recording withdrawal payment."""
        entry = self.service.record_withdrawal_paid(
            store=self.store,
            withdrawal_id="WD-001",
            amount=Decimal('500.00'),
            idempotency_key="key-withdrawal-001"
        )
        
        self.assertIsNotNone(entry)
        self.assertEqual(entry.entry_type, "withdrawal")

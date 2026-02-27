"""
Test suite for wallet models.
Tests Account, JournalEntry, JournalLine, FeePolicy, and PaymentAllocation models.
"""
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import User

from apps.stores.models import Store, StoreType
from apps.tenants.models import Tenant
from apps.wallet.models import (
    Wallet, WalletTransaction, WithdrawalRequest,
    Account, JournalEntry, JournalLine, FeePolicy, PaymentAllocation
)


class AccountModelTestCase(TestCase):
    """Test Account (Chart of Accounts) model."""
    
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
    
    def test_create_account(self):
        """Test creating a chart of accounts entry."""
        account = Account.objects.create(
            store=self.store,
            code="1000",
            name="Cash",
            account_type="asset",
            parent_account=None
        )
        self.assertEqual(account.code, "1000")
        self.assertEqual(account.name, "Cash")
        self.assertEqual(account.account_type, "asset")
        self.assertTrue(account.is_active)
    
    def test_account_uniqueness(self):
        """Test that store + code combination is unique."""
        Account.objects.create(
            store=self.store,
            code="1000",
            name="Cash",
            account_type="asset"
        )
        
        with self.assertRaises(Exception):  # IntegrityError
            Account.objects.create(
                store=self.store,
                code="1000",
                name="Duplicate Cash",
                account_type="asset"
            )
    
    def test_account_types(self):
        """Test all account types can be created."""
        types = ['asset', 'liability', 'equity', 'revenue', 'expense']
        for acc_type in types:
            account = Account.objects.create(
                store=self.store,
                code=f"code-{acc_type}",
                name=f"Test {acc_type}",
                account_type=acc_type
            )
            self.assertEqual(account.account_type, acc_type)
    
    def test_deactivate_account(self):
        """Test deactivating an account."""
        account = Account.objects.create(
            store=self.store,
            code="1000",
            name="Cash",
            account_type="asset",
            is_active=True
        )
        account.is_active = False
        account.save()
        
        refreshed = Account.objects.get(id=account.id)
        self.assertFalse(refreshed.is_active)


class JournalEntryModelTestCase(TestCase):
    """Test JournalEntry (double-entry ledger) model."""
    
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
        
        # Create accounts
        self.cash_account = Account.objects.create(
            store=self.store,
            code="1000",
            name="Cash",
            account_type="asset"
        )
        self.payable_account = Account.objects.create(
            store=self.store,
            code="2000",
            name="Payable",
            account_type="liability"
        )
    
    def test_create_journal_entry(self):
        """Test creating a journal entry."""
        entry = JournalEntry.objects.create(
            store=self.store,
            entry_date=timezone.now().date(),
            entry_type="payment_captured",
            reference_id="ORD-123",
            description="Order payment",
            idempotency_key="unique-key-123"
        )
        self.assertEqual(entry.entry_type, "payment_captured")
        self.assertEqual(entry.status, "posted")
    
    def test_entry_balanced(self):
        """Test that balanced entry validates correctly."""
        entry = JournalEntry.objects.create(
            store=self.store,
            entry_date=timezone.now().date(),
            entry_type="payment_captured",
            reference_id="ORD-123",
            description="Order payment",
            idempotency_key="unique-key-123"
        )
        
        # Add balanced lines
        JournalLine.objects.create(
            journal_entry=entry,
            account=self.cash_account,
            debit=Decimal('100.00'),
            credit=Decimal('0.00')
        )
        JournalLine.objects.create(
            journal_entry=entry,
            account=self.payable_account,
            debit=Decimal('0.00'),
            credit=Decimal('100.00')
        )
        
        # Should validate without error
        is_balanced = entry.validate_balanced()
        self.assertTrue(is_balanced)
    
    def test_entry_unbalanced(self):
        """Test that unbalanced entry raises validation error."""
        entry = JournalEntry.objects.create(
            store=self.store,
            entry_date=timezone.now().date(),
            entry_type="payment_captured",
            reference_id="ORD-123",
            description="Order payment",
            idempotency_key="unique-key-123"
        )
        
        # Add unbalanced lines
        JournalLine.objects.create(
            journal_entry=entry,
            account=self.cash_account,
            debit=Decimal('100.00'),
            credit=Decimal('0.00')
        )
        JournalLine.objects.create(
            journal_entry=entry,
            account=self.payable_account,
            debit=Decimal('0.00'),
            credit=Decimal('50.00')
        )
        
        with self.assertRaises(ValidationError):
            entry.validate_balanced()
    
    def test_idempotency_key_uniqueness(self):
        """Test idempotency key is unique per store."""
        JournalEntry.objects.create(
            store=self.store,
            entry_date=timezone.now().date(),
            entry_type="payment_captured",
            reference_id="ORD-123",
            idempotency_key="unique-key"
        )
        
        # Same key should not be allowed for same store
        with self.assertRaises(Exception):
            JournalEntry.objects.create(
                store=self.store,
                entry_date=timezone.now().date(),
                entry_type="payment_captured",
                reference_id="ORD-124",
                idempotency_key="unique-key"
            )
    
    def test_entry_types(self):
        """Test all entry types can be created."""
        types = ['payment_captured', 'order_delivered', 'refund', 'withdrawal', 'adjustment']
        for entry_type in types:
            entry = JournalEntry.objects.create(
                store=self.store,
                entry_date=timezone.now().date(),
                entry_type=entry_type,
                reference_id=f"REF-{entry_type}",
                idempotency_key=f"key-{entry_type}"
            )
            self.assertEqual(entry.entry_type, entry_type)


class JournalLineModelTestCase(TestCase):
    """Test JournalLine (individual debit/credit) model."""
    
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
        
        self.account = Account.objects.create(
            store=self.store,
            code="1000",
            name="Cash",
            account_type="asset"
        )
        
        self.entry = JournalEntry.objects.create(
            store=self.store,
            entry_date=timezone.now().date(),
            entry_type="payment_captured",
            reference_id="ORD-123",
            idempotency_key="key-123"
        )
    
    def test_create_debit_line(self):
        """Test creating a debit journal line."""
        line = JournalLine.objects.create(
            journal_entry=self.entry,
            account=self.account,
            debit=Decimal('100.00'),
            credit=Decimal('0.00')
        )
        self.assertEqual(line.debit, Decimal('100.00'))
        self.assertEqual(line.credit, Decimal('0.00'))
    
    def test_create_credit_line(self):
        """Test creating a credit journal line."""
        line = JournalLine.objects.create(
            journal_entry=self.entry,
            account=self.account,
            debit=Decimal('0.00'),
            credit=Decimal('50.00')
        )
        self.assertEqual(line.debit, Decimal('0.00'))
        self.assertEqual(line.credit, Decimal('50.00'))
    
    def test_line_both_debit_credit_invalid(self):
        """Test that having both debit and credit is invalid."""
        line = JournalLine(
            journal_entry=self.entry,
            account=self.account,
            debit=Decimal('100.00'),
            credit=Decimal('50.00')
        )
        # Should raise validation error
        with self.assertRaises(ValidationError):
            line.full_clean()
    
    def test_line_zero_amount_invalid(self):
        """Test that zero amount is invalid."""
        line = JournalLine(
            journal_entry=self.entry,
            account=self.account,
            debit=Decimal('0.00'),
            credit=Decimal('0.00')
        )
        with self.assertRaises(ValidationError):
            line.full_clean()


class FeePolicyModelTestCase(TestCase):
    """Test FeePolicy model."""
    
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
    
    def test_create_percentage_policy(self):
        """Test creating a percentage-based fee policy."""
        policy = FeePolicy.objects.create(
            name="Standard Commission",
            fee_type="percentage",
            fee_value=Decimal('2.50'),
            scope="global"
        )
        self.assertEqual(policy.fee_type, "percentage")
        self.assertEqual(policy.fee_value, Decimal('2.50'))
        self.assertTrue(policy.is_active)
    
    def test_create_fixed_policy(self):
        """Test creating a fixed-amount fee policy."""
        policy = FeePolicy.objects.create(
            name="Per-Order Fee",
            fee_type="fixed",
            fee_value=Decimal('0.50'),
            scope="global"
        )
        self.assertEqual(policy.fee_type, "fixed")
        self.assertEqual(policy.fee_value, Decimal('0.50'))
    
    def test_store_level_policy(self):
        """Test creating a store-specific fee policy."""
        policy = FeePolicy.objects.create(
            name="Premium Store Rate",
            fee_type="percentage",
            fee_value=Decimal('1.50'),
            scope="store",
            store=self.store
        )
        self.assertEqual(policy.scope, "store")
        self.assertEqual(policy.store, self.store)
    
    def test_minimum_fee(self):
        """Test minimum fee constraint."""
        policy = FeePolicy.objects.create(
            name="With Minimum",
            fee_type="percentage",
            fee_value=Decimal('2.00'),
            minimum_fee=Decimal('1.00'),
            scope="global"
        )
        self.assertEqual(policy.minimum_fee, Decimal('1.00'))
    
    def test_deactivate_policy(self):
        """Test deactivating a policy."""
        policy = FeePolicy.objects.create(
            name="Test Policy",
            fee_type="percentage",
            fee_value=Decimal('2.50'),
            scope="global",
            is_active=True
        )
        policy.is_active = False
        policy.save()
        
        refreshed = FeePolicy.objects.get(id=policy.id)
        self.assertFalse(refreshed.is_active)


class PaymentAllocationModelTestCase(TestCase):
    """Test PaymentAllocation model."""
    
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
        
        self.entry = JournalEntry.objects.create(
            store=self.store,
            entry_date=timezone.now().date(),
            entry_type="payment_captured",
            reference_id="ORD-123",
            idempotency_key="key-123"
        )
        
        self.policy = FeePolicy.objects.create(
            name="Standard",
            fee_type="percentage",
            fee_value=Decimal('2.50'),
            scope="global"
        )
    
    def test_create_allocation(self):
        """Test creating a payment allocation (fee split)."""
        allocation = PaymentAllocation.objects.create(
            journal_entry=self.entry,
            fee_policy=self.policy,
            gross_amount=Decimal('100.00'),
            fee_amount=Decimal('2.50'),
            net_amount=Decimal('97.50'),
            allocation_data={
                'order_id': 123,
                'description': 'Test order'
            }
        )
        self.assertEqual(allocation.gross_amount, Decimal('100.00'))
        self.assertEqual(allocation.fee_amount, Decimal('2.50'))
        self.assertEqual(allocation.net_amount, Decimal('97.50'))
    
    def test_allocation_totals_match(self):
        """Test that allocation amounts are consistent."""
        allocation = PaymentAllocation.objects.create(
            journal_entry=self.entry,
            fee_policy=self.policy,
            gross_amount=Decimal('100.00'),
            fee_amount=Decimal('2.50'),
            net_amount=Decimal('97.50')
        )
        # Verify: gross = fee + net
        self.assertEqual(
            allocation.gross_amount,
            allocation.fee_amount + allocation.net_amount
        )


class WithdrawalRequestEnhancementTestCase(TestCase):
    """Test enhanced WithdrawalRequest model fields."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", domain="test.local")
        self.owner = User.objects.create_user(username="testuser", password="pass123")
        self.admin = User.objects.create_user(username="admin", password="pass123")
        self.store = Store.objects.create(
            name="Test Store",
            owner=self.owner,
            tenant=self.tenant,
            store_type=StoreType.INDIVIDUAL,
            subdomain="test-store"
        )
        self.wallet = Wallet.objects.create(store=self.store)
        
        self.entry = JournalEntry.objects.create(
            store=self.store,
            entry_date=timezone.now().date(),
            entry_type="withdrawal",
            reference_id="WD-001",
            idempotency_key="key-withdrawal-1"
        )
    
    def test_withdrawal_with_new_fields(self):
        """Test withdrawal created with new fields."""
        withdrawal = WithdrawalRequest.objects.create(
            store=self.store,
            amount=Decimal('500.00'),
            requested_by=self.owner,
            approved_by=self.admin,
            payout_reference="BANK-123",
            rejection_reason="",
            journal_entry=self.entry
        )
        self.assertEqual(withdrawal.requested_by, self.owner)
        self.assertEqual(withdrawal.approved_by, self.admin)
        self.assertEqual(withdrawal.payout_reference, "BANK-123")
    
    def test_withdrawal_approval_flow(self):
        """Test withdrawal approval state transitions."""
        withdrawal = WithdrawalRequest.objects.create(
            store=self.store,
            amount=Decimal('500.00'),
            status="pending",
            requested_by=self.owner
        )
        
        # Move to approved
        withdrawal.status = "approved"
        withdrawal.approved_by = self.admin
        withdrawal.save()
        
        # Move to paid
        withdrawal.status = "paid"
        withdrawal.payout_reference = "BANK-456"
        withdrawal.processed_at = timezone.now()
        withdrawal.save()
        
        refreshed = WithdrawalRequest.objects.get(id=withdrawal.id)
        self.assertEqual(refreshed.status, "paid")
        self.assertEqual(refreshed.payout_reference, "BANK-456")
    
    def test_rejection_reason(self):
        """Test rejection with reason."""
        withdrawal = WithdrawalRequest.objects.create(
            store=self.store,
            amount=Decimal('500.00'),
            status="pending",
            requested_by=self.owner
        )
        
        withdrawal.status = "rejected"
        withdrawal.rejection_reason = "Insufficient balance verification"
        withdrawal.processed_at = timezone.now()
        withdrawal.save()
        
        refreshed = WithdrawalRequest.objects.get(id=withdrawal.id)
        self.assertEqual(refreshed.status, "rejected")
        self.assertIn("Insufficient", refreshed.rejection_reason)

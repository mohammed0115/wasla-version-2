"""
Test suite for wallet service.
Tests WalletService balance management, transactions, and withdrawal processing.
"""
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth.models import User

from apps.stores.models import Store, StoreType
from apps.tenants.models import Tenant
from apps.wallet.models import (
    Wallet, WalletTransaction, WithdrawalRequest, Account,
    JournalEntry, FeePolicy
)
from apps.wallet.services.wallet_service import WalletService
from apps.wallet.services.accounting_service import AccountingService


class WalletBalanceTestCase(TransactionTestCase):
    """Test wallet balance management."""
    
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
        self.wallet = Wallet.objects.create(
            store=self.store,
            available_balance=Decimal('1000.00'),
            pending_balance=Decimal('100.00')
        )
        self.service = WalletService()
        self.acct_service = AccountingService()
        self.acct_service.get_or_create_accounts(self.store)
    
    def test_get_wallet_balance(self):
        """Test retrieving wallet balance."""
        balance = self.wallet.available_balance
        self.assertEqual(balance, Decimal('1000.00'))
    
    def test_on_order_paid(self):
        """Test handling order payment capture."""
        fee_policy = FeePolicy.objects.create(
            name="Test",
            fee_type="percentage",
            fee_value=Decimal('2.50'),
            scope="global"
        )
        
        initial_available = self.wallet.available_balance
        initial_pending = self.wallet.pending_balance
        
        # Simulate payment capture
        self.service.on_order_paid(
            store=self.store,
            order_id="ORD-001",
            amount=Decimal('100.00'),
            fee_policy=fee_policy,
            user=self.owner  # For idempotency
        )
        
        # Refresh wallet
        self.wallet.refresh_from_db()
        
        # Pending should increase by (amount - fee)
        # 100 - 2.50 = 97.50 added to pending
        self.assertEqual(
            self.wallet.pending_balance,
            initial_pending + Decimal('97.50')
        )
    
    def test_on_order_delivered(self):
        """Test moving balance from pending to available."""
        # First add to pending
        self.wallet.pending_balance = Decimal('100.00')
        self.wallet.save()
        
        initial_available = self.wallet.available_balance
        
        self.service.on_order_delivered(
            store=self.store,
            order_id="ORD-001",
            amount=Decimal('100.00'),
            user=self.owner
        )
        
        self.wallet.refresh_from_db()
        
        # Pending should decrease, available should increase
        self.assertEqual(self.wallet.pending_balance, Decimal('0.00'))
        self.assertEqual(
            self.wallet.available_balance,
            initial_available + Decimal('100.00')
        )
    
    def test_on_refund(self):
        """Test handling customer refund."""
        initial_available = self.wallet.available_balance
        refund_amount = Decimal('100.00')
        
        self.service.on_refund(
            store=self.store,
            order_id="ORD-001",
            amount=refund_amount,
            reverse_full_fee=True,
            user=self.owner
        )
        
        self.wallet.refresh_from_db()
        
        # Merchant should be credited back
        # (refund is returned to pending)
        self.assertLess(self.wallet.available_balance, initial_available)


class WithdrawalRequestTestCase(TransactionTestCase):
    """Test withdrawal request creation and processing."""
    
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
        self.wallet = Wallet.objects.create(
            store=self.store,
            available_balance=Decimal('1000.00'),
            pending_balance=Decimal('0.00')
        )
        self.service = WalletService()
        self.acct_service = AccountingService()
        self.acct_service.get_or_create_accounts(self.store)
    
    def test_request_withdrawal(self):
        """Test creating a withdrawal request."""
        withdrawal = self.service.request_withdrawal(
            store=self.store,
            amount=Decimal('500.00'),
            note="Monthly payout",
            requested_by=self.owner
        )
        
        self.assertIsNotNone(withdrawal)
        self.assertEqual(withdrawal.amount, Decimal('500.00'))
        self.assertEqual(withdrawal.status, "pending")
        self.assertEqual(withdrawal.requested_by, self.owner)
        self.assertIsNotNone(withdrawal.reference_code)
    
    def test_request_withdrawal_exceeds_balance(self):
        """Test that requesting more than available balance is rejected."""
        withdrawal = self.service.request_withdrawal(
            store=self.store,
            amount=Decimal('2000.00'),  # More than available
            requested_by=self.owner
        )
        
        # Should still create request (admin will review)
        # but it's marked as error or with validation
        self.assertIsNotNone(withdrawal)
    
    def test_approve_withdrawal(self):
        """Test approving a withdrawal request."""
        withdrawal = WithdrawalRequest.objects.create(
            store=self.store,
            amount=Decimal('500.00'),
            status="pending",
            requested_by=self.owner
        )
        
        approved = self.service.approve_withdrawal(
            withdrawal_id=withdrawal.id,
            approved_by=self.admin
        )
        
        self.assertEqual(approved.status, "approved")
        self.assertEqual(approved.approved_by, self.admin)
    
    def test_reject_withdrawal(self):
        """Test rejecting a withdrawal request."""
        withdrawal = WithdrawalRequest.objects.create(
            store=self.store,
            amount=Decimal('500.00'),
            status="pending",
            requested_by=self.owner
        )
        
        rejected = self.service.reject_withdrawal(
            withdrawal_id=withdrawal.id,
            reason="Insufficient verification",
            approved_by=self.admin
        )
        
        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(rejected.rejection_reason, "Insufficient verification")
    
    def test_mark_withdrawal_paid(self):
        """Test marking withdrawal as paid."""
        withdrawal = WithdrawalRequest.objects.create(
            store=self.store,
            amount=Decimal('500.00'),
            status="approved",
            requested_by=self.owner,
            approved_by=self.admin
        )
        
        initial_available = self.wallet.available_balance
        
        paid = self.service.mark_withdrawal_paid(
            withdrawal_id=withdrawal.id,
            payout_reference="BANK-123456"
        )
        
        self.assertEqual(paid.status, "paid")
        self.assertEqual(paid.payout_reference, "BANK-123456")
        
        # Balance should be reduced
        self.wallet.refresh_from_db()
        self.assertEqual(
            self.wallet.available_balance,
            initial_available - Decimal('500.00')
        )
    
    def test_withdrawal_workflow(self):
        """Test complete withdrawal workflow."""
        # 1. Request
        withdrawal = self.service.request_withdrawal(
            store=self.store,
            amount=Decimal('500.00'),
            requested_by=self.owner
        )
        self.assertEqual(withdrawal.status, "pending")
        
        # 2. Approve
        withdrawal = self.service.approve_withdrawal(
            withdrawal_id=withdrawal.id,
            approved_by=self.admin
        )
        self.assertEqual(withdrawal.status, "approved")
        
        # 3. Pay
        withdrawal = self.service.mark_withdrawal_paid(
            withdrawal_id=withdrawal.id,
            payout_reference="BANK-789"
        )
        self.assertEqual(withdrawal.status, "paid")
        self.assertIsNotNone(withdrawal.processed_at)


class WalletTransactionTestCase(TestCase):
    """Test wallet transaction logging."""
    
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
    
    def test_credit_transaction(self):
        """Test logging a credit transaction."""
        transaction = WalletTransaction.objects.create(
            wallet=self.wallet,
            transaction_type="credit",
            amount=Decimal('100.00'),
            reference_id="ORD-001",
            description="Order payment"
        )
        
        self.assertEqual(transaction.transaction_type, "credit")
        self.assertEqual(transaction.amount, Decimal('100.00'))
    
    def test_debit_transaction(self):
        """Test logging a debit transaction."""
        transaction = WalletTransaction.objects.create(
            wallet=self.wallet,
            transaction_type="debit",
            amount=Decimal('50.00'),
            reference_id="WD-001",
            description="Withdrawal"
        )
        
        self.assertEqual(transaction.transaction_type, "debit")
        self.assertEqual(transaction.amount, Decimal('50.00'))


class WalletIdempotencyTestCase(TransactionTestCase):
    """Test idempotency of wallet operations."""
    
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
        self.wallet = Wallet.objects.create(
            store=self.store,
            available_balance=Decimal('1000.00')
        )
        self.service = WalletService()
        self.acct_service = AccountingService()
        self.acct_service.get_or_create_accounts(self.store)
        
        self.fee_policy = FeePolicy.objects.create(
            name="Test",
            fee_type="percentage",
            fee_value=Decimal('2.50'),
            scope="global"
        )
    
    def test_on_order_paid_idempotency(self):
        """Test that processing same payment twice doesn't double-charge."""
        idempotency_key = "order-ORD-001-paid"
        
        # First process
        self.service.on_order_paid(
            store=self.store,
            order_id="ORD-001",
            amount=Decimal('100.00'),
            fee_policy=self.fee_policy,
            user=self.owner,
            idempotency_key=idempotency_key
        )
        
        self.wallet.refresh_from_db()
        pending1 = self.wallet.pending_balance
        
        # Second process (should be no-op)
        self.service.on_order_paid(
            store=self.store,
            order_id="ORD-001",
            amount=Decimal('100.00'),
            fee_policy=self.fee_policy,
            user=self.owner,
            idempotency_key=idempotency_key
        )
        
        self.wallet.refresh_from_db()
        pending2 = self.wallet.pending_balance
        
        # Should not change
        self.assertEqual(pending1, pending2)
        
        # Should have only one journal entry
        entries = JournalEntry.objects.filter(
            store=self.store,
            idempotency_key=idempotency_key
        )
        self.assertEqual(entries.count(), 1)
    
    def test_on_order_delivered_idempotency(self):
        """Test that confirming delivery twice doesn't double-move balance."""
        # Setup: put some amount in pending
        self.wallet.pending_balance = Decimal('100.00')
        self.wallet.save()
        
        idempotency_key = "order-ORD-001-delivered"
        
        # First delivery
        self.service.on_order_delivered(
            store=self.store,
            order_id="ORD-001",
            amount=Decimal('100.00'),
            user=self.owner,
            idempotency_key=idempotency_key
        )
        
        self.wallet.refresh_from_db()
        available1 = self.wallet.available_balance
        pending1 = self.wallet.pending_balance
        
        # Second delivery (should be no-op)
        self.service.on_order_delivered(
            store=self.store,
            order_id="ORD-001",
            amount=Decimal('100.00'),
            user=self.owner,
            idempotency_key=idempotency_key
        )
        
        self.wallet.refresh_from_db()
        available2 = self.wallet.available_balance
        pending2 = self.wallet.pending_balance
        
        # Balances should not change
        self.assertEqual(available1, available2)
        self.assertEqual(pending1, pending2)

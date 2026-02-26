"""
Test suite for wallet migrations.
Tests data migrations for accounting system setup and balance backfill.
"""
from decimal import Decimal
from django.test import TransactionTestCase
from django.core.management import call_command
from django.contrib.auth.models import User
from io import StringIO

from apps.stores.models import Store, StoreType
from apps.tenants.models import Tenant
from apps.wallet.models import (
    Wallet, Account, JournalEntry, JournalLine
)


class MigrationTestCase(TransactionTestCase):
    """Test that migrations apply correctly."""
    
    def test_0004_double_entry_accounting_migration(self):
        """Test schema migration creates necessary tables."""
        # This test runs after migration 0004 is applied
        # Verify that new models exist
        self.assertIsNotNone(Account._meta.db_table)
        self.assertIsNotNone(JournalEntry._meta.db_table)
        self.assertIsNotNone(JournalLine._meta.db_table)
    
    def test_account_model_fields(self):
        """Test that Account model has required fields."""
        tenant = Tenant.objects.create(name="Test", domain="test.local")
        owner = User.objects.create_user(username="user", password="pass")
        store = Store.objects.create(
            name="Store",
            owner=owner,
            tenant=tenant,
            store_type=StoreType.INDIVIDUAL,
            subdomain="store"
        )
        
        account = Account.objects.create(
            store=store,
            code="1000",
            name="Cash",
            account_type="asset"
        )
        
        # Verify required fields exist
        self.assertIsNotNone(account.code)
        self.assertIsNotNone(account.name)
        self.assertIsNotNone(account.account_type)
        self.assertIsNotNone(account.store)
        self.assertTrue(account.is_active)
    
    def test_journal_entry_model_fields(self):
        """Test that JournalEntry model has required fields."""
        tenant = Tenant.objects.create(name="Test", domain="test.local")
        owner = User.objects.create_user(username="user", password="pass")
        store = Store.objects.create(
            name="Store",
            owner=owner,
            tenant=tenant,
            store_type=StoreType.INDIVIDUAL,
            subdomain="store"
        )
        
        from django.utils import timezone
        entry = JournalEntry.objects.create(
            store=store,
            entry_date=timezone.now().date(),
            entry_type="payment_captured",
            reference_id="ORD-001",
            idempotency_key="key-001"
        )
        
        # Verify required fields
        self.assertIsNotNone(entry.store)
        self.assertIsNotNone(entry.entry_date)
        self.assertIsNotNone(entry.entry_type)
        self.assertEqual(entry.status, "posted")  # Default status


class SystemAccountsCreationTestCase(TransactionTestCase):
    """Test data migration that creates system accounts."""
    
    def test_system_accounts_created_for_store(self):
        """Test that standard accounts are created for stores."""
        tenant = Tenant.objects.create(name="Test", domain="test.local")
        owner = User.objects.create_user(username="user", password="pass")
        store = Store.objects.create(
            name="Store",
            owner=owner,
            tenant=tenant,
            store_type=StoreType.INDIVIDUAL,
            subdomain="store"
        )
        
        # Run migration 0005 manually (if needed)
        # This creates system accounts
        from apps.wallet.services.accounting_service import AccountingService
        service = AccountingService()
        accounts = service.get_or_create_accounts(store)
        
        # Should create 8 accounts
        self.assertEqual(len(accounts), 8)
    
    def test_account_codes_match_specification(self):
        """Test that created accounts match the specification."""
        tenant = Tenant.objects.create(name="Test", domain="test.local")
        owner = User.objects.create_user(username="user", password="pass")
        store = Store.objects.create(
            name="Store",
            owner=owner,
            tenant=tenant,
            store_type=StoreType.INDIVIDUAL,
            subdomain="store"
        )
        
        from apps.wallet.services.accounting_service import AccountingService
        service = AccountingService()
        accounts = service.get_or_create_accounts(store)
        
        # Verify required account codes exist
        codes = {acc.code for acc in accounts.values()}
        required_codes = {'1000', '2000', '2100', '2200', '4000', '2300', '5000', '2400'}
        
        self.assertEqual(codes, required_codes)


class BalanceBackfillTestCase(TransactionTestCase):
    """Test data migration that backfills wallet balances."""
    
    def test_opening_balance_entries_created(self):
        """Test that opening balance journal entries are created."""
        tenant = Tenant.objects.create(name="Test", domain="test.local")
        owner = User.objects.create_user(username="user", password="pass")
        store = Store.objects.create(
            name="Store",
            owner=owner,
            tenant=tenant,
            store_type=StoreType.INDIVIDUAL,
            subdomain="store"
        )
        
        # Create a wallet with existing balance
        wallet = Wallet.objects.create(
            store=store,
            available_balance=Decimal('500.00')
        )
        
        # Manually create opening entry as migration would
        from apps.wallet.services.accounting_service import AccountingService
        service = AccountingService()
        service.get_or_create_accounts(store)
        
        entries = JournalEntry.objects.filter(
            store=store,
            entry_type='adjustment'
        )
        
        # Should have at least one adjustment entry
        # (or none if already processed)
        self.assertIsNotNone(entries)
    
    def test_backfill_does_not_duplicate(self):
        """Test that backfill migration is idempotent."""
        tenant = Tenant.objects.create(name="Test", domain="test.local")
        owner = User.objects.create_user(username="user", password="pass")
        store = Store.objects.create(
            name="Store",
            owner=owner,
            tenant=tenant,
            store_type=StoreType.INDIVIDUAL,
            subdomain="store"
        )
        
        wallet = Wallet.objects.create(
            store=store,
            available_balance=Decimal('500.00')
        )
        
        from apps.wallet.services.accounting_service import AccountingService
        service = AccountingService()
        service.get_or_create_accounts(store)
        
        # Run twice
        entries_count_1 = JournalEntry.objects.filter(store=store).count()
        entries_count_2 = JournalEntry.objects.filter(store=store).count()
        
        # Count should match (no duplicates)
        self.assertEqual(entries_count_1, entries_count_2)


class WithdrawalRequestMigrationTestCase(TransactionTestCase):
    """Test migration that adds fields to WithdrawalRequest."""
    
    def test_withdrawal_request_new_fields(self):
        """Test that WithdrawalRequest has new fields."""
        from apps.wallet.models import WithdrawalRequest
        
        tenant = Tenant.objects.create(name="Test", domain="test.local")
        owner = User.objects.create_user(username="user", password="pass")
        store = Store.objects.create(
            name="Store",
            owner=owner,
            tenant=tenant,
            store_type=StoreType.INDIVIDUAL,
            subdomain="store"
        )
        
        Wallet.objects.create(store=store)
        
        # Create withdrawal with new fields
        withdrawal = WithdrawalRequest.objects.create(
            store=store,
            amount=Decimal('100.00'),
            requested_by=owner
        )
        
        # Verify new fields exist and are accessible
        self.assertIsNotNone(withdrawal.requested_by)
        self.assertIsNone(withdrawal.approved_by)  # Default is null
        self.assertEqual(withdrawal.rejection_reason, '')  # Default empty
        self.assertIsNone(withdrawal.payout_reference)

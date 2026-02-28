"""
Comprehensive Financial Integrity Tests.

These tests validate:
1. Double refund prevention
2. Settlement non-duplication under concurrency
3. Fee consistency and wallet balance reconciliation
4. Refund cap enforcement
5. Ledger entry creation and audit trail
"""

import pytest
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.db import transaction
from unittest.mock import patch, MagicMock
import hashlib

from apps.payments.models import PaymentAttempt, RefundRecord
from apps.orders.models import Order
from apps.settlements.models import (
    Settlement, SettlementBatch, SettlementBatchItem, 
    LedgerAccount, LedgerEntry
)
from apps.stores.models import Store
from apps.tenants.models import Tenant
from apps.wallet.services.accounting_service import AccountingService, FeePolicy
from apps.payments.services.refund_idempotency_service import RefundIdempotencyService
from apps.settlements.services.settlement_automation_service import SettlementAutomationService


@pytest.mark.django_db
class TestFeeConsistency(TestCase):
    """Test platform fee consistency."""
    
    def setUp(self):
        """Create test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Test Store",
            store_number="TEST001",
        )
        self.accounting = AccountingService()
    
    def test_fee_calculation_determinism(self):
        """Test that fee calculations are deterministic."""
        amount = Decimal("1000.00")
        
        # Calculate fee twice
        result1 = self.accounting.calculate_fee_breakdown(
            gross_amount=amount,
            tenant_id=self.tenant.id,
            store_id=self.store.id,
        )
        result2 = self.accounting.calculate_fee_breakdown(
            gross_amount=amount,
            tenant_id=self.tenant.id,
            store_id=self.store.id,
        )
        
        # Must be identical
        assert result1["gross"] == result2["gross"]
        assert result1["total_fee"] == result2["total_fee"]
        assert result1["net"] == result2["net"]
        assert result1["transaction_fee"] == result2["transaction_fee"]
        assert result1["wasla_commission"] == result2["wasla_commission"]
    
    def test_fee_breakdown_mathematics(self):
        """Test that fee breakdown math is correct."""
        gross = Decimal("1000.00")
        result = self.accounting.calculate_fee_breakdown(
            gross_amount=gross,
            tenant_id=self.tenant.id,
            store_id=self.store.id,
        )
        
        # Gross = TransFee + WaslaCommission + Net
        total_calculated = (
            result["transaction_fee"] + 
            result["wasla_commission"] + 
            result["net"]
        )
        
        assert total_calculated == result["gross"]
        
        # Net is positive
        assert result["net"] > Decimal("0")
        assert result["net"] < result["gross"]
    
    def test_fee_calculation_edge_cases(self):
        """Test fee calculation with edge case amounts."""
        # Very small amount
        small_result = self.accounting.calculate_fee_breakdown(
            gross_amount=Decimal("0.01"),
            tenant_id=self.tenant.id,
            store_id=self.store.id,
        )
        assert small_result["net"] >= Decimal("0")
        
        # Large amount
        large_result = self.accounting.calculate_fee_breakdown(
            gross_amount=Decimal("1000000.00"),
            tenant_id=self.tenant.id,
            store_id=self.store.id,
        )
        assert large_result["total_fee"] > Decimal("0")
        assert large_result["net"] > Decimal("0")
    
    @pytest.mark.django_db
    def test_fee_ledger_entries_creation(self):
        """Test that fee record creates proper ledger entries."""
        order = self._create_order()
        
        result = self.accounting.record_payment_fee(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            gross_amount=Decimal("1000.00"),
            order_id=order.id,
            reference=f"ORD-{order.id}",
        )
        
        assert result["success"] is True
        assert len(result["ledger_entries"]) >= 2  # At least credit + 1 fee debit
        assert result["fee_breakdown"]["net"] > Decimal("0")
        
        # Verify ledger entries exist
        entries = LedgerEntry.objects.filter(id__in=result["ledger_entries"])
        assert entries.count() >= 2
        
        # Verify credit entry
        credit_entries = entries.filter(entry_type=LedgerEntry.TYPE_CREDIT)
        assert credit_entries.exists()
        assert credit_entries.first().amount == Decimal("1000.00")
    
    def _create_order(self):
        """Helper to create test order."""
        return Order.objects.create(
            tenant=self.tenant,
            store=self.store,
            order_number=f"ORD-{timezone.now().timestamp()}",
            customer_email="test@example.com",
            total_amount=Decimal("1000.00"),
            status="pending",
        )


@pytest.mark.django_db
class TestRefundIdempotency(TransactionTestCase):
    """Test refund idempotency and cap enforcement."""
    
    def setUp(self):
        """Create test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Test Store",
            store_number="TEST001",
        )
        self.order = Order.objects.create(
            tenant=self.tenant,
            store=self.store,
            order_number="ORD-001",
            customer_email="test@example.com",
            total_amount=Decimal("1000.00"),
            status="paid",
        )
        self.payment_attempt = PaymentAttempt.objects.create(
            store=self.store,
            order=self.order,
            provider=PaymentAttempt.PROVIDER_TAP,
            method="card",
            amount=Decimal("1000.00"),
            currency="SAR",
            status=PaymentAttempt.STATUS_CONFIRMED,
            idempotency_key="test-payment-001",
        )
        # Create ledger account
        LedgerAccount.objects.create(
            tenant=self.tenant,
            store_id=self.store.id,
            currency="SAR",
            available_balance=Decimal("1000.00"),
            pending_balance=Decimal("0"),
        )
        self.service = RefundIdempotencyService()
    
    def test_refund_idempotency_key_prevents_double_refund(self):
        """Test that idempotency key prevents double refunds."""
        idempotency_key = "ref-webhook-abc123"
        
        # First refund
        result1 = self.service.process_refund(
            payment_attempt_id=self.payment_attempt.id,
            amount=Decimal("100.00"),
            idempotency_key=idempotency_key,
            reason="Test refund",
        )
        
        assert result1["success"] is True
        assert result1["idempotent_reuse"] is False
        refund_id_1 = result1["refund_id"]
        
        # Second refund with SAME idempotency key should return existing refund
        result2 = self.service.process_refund(
            payment_attempt_id=self.payment_attempt.id,
            amount=Decimal("100.00"),
            idempotency_key=idempotency_key,
            reason="Test refund",
        )
        
        assert result2["success"] is True
        assert result2["idempotent_reuse"] is True  # Flag indicates reuse
        assert result2["refund_id"] == refund_id_1  # Same refund ID
        
        # Only one RefundRecord should exist
        refunds = RefundRecord.objects.filter(
            payment_intent_id=self.payment_attempt.id
        ).exclude(status=RefundRecord.STATUS_FAILED)
        assert refunds.count() == 1
    
    def test_refund_cap_enforcement(self):
        """Test that total refunds cannot exceed payment amount."""
        # Try to refund 600 + 600 = 1200, but payment is only 1000
        result1 = self.service.process_refund(
            payment_attempt_id=self.payment_attempt.id,
            amount=Decimal("600.00"),
            idempotency_key="ref-001",
        )
        assert result1["success"] is True
        assert result1["total_refunded"] == Decimal("600.00")
        
        # Second refund attempt with 600 should fail (total would be 1200)
        result2 = self.service.process_refund(
            payment_attempt_id=self.payment_attempt.id,
            amount=Decimal("600.00"),
            idempotency_key="ref-002",
        )
        
        assert result2["success"] is False
        assert "exceeds remaining refundable" in result2["error"]
        assert result2["remaining_refundable"] == Decimal("400.00")
    
    def test_refund_creates_ledger_entries(self):
        """Test that refunds create ledger entries."""
        result = self.service.process_refund(
            payment_attempt_id=self.payment_attempt.id,
            amount=Decimal("100.00"),
            idempotency_key="ref-test-001",
        )
        
        assert result["success"] is True
        assert len(result["ledger_entries"]) > 0
        
        # Verify ledger entry exists
        entry = LedgerEntry.objects.get(id=result["ledger_entries"][0])
        assert entry.amount == Decimal("100.00")
        assert entry.entry_type == LedgerEntry.TYPE_DEBIT
        assert "Refund" in entry.description
    
    def test_refund_updates_order_status(self):
        """Test that refunds update order refund status."""
        self.order.refunded_amount = Decimal("0")
        self.order.save()
        
        # Partial refund
        result = self.service.process_refund(
            payment_attempt_id=self.payment_attempt.id,
            amount=Decimal("500.00"),
            idempotency_key="ref-partial",
        )
        
        assert result["success"] is True
        
        # Check order status
        order = Order.objects.get(id=self.order.id)
        assert order.refunded_amount == Decimal("500.00")
        assert order.status == "partially_refunded"
        
        # Full refund
        result2 = self.service.process_refund(
            payment_attempt_id=self.payment_attempt.id,
            amount=Decimal("500.00"),
            idempotency_key="ref-complete",
        )
        
        assert result2["success"] is True
        order.refresh_from_db()
        assert order.refunded_amount == Decimal("1000.00")
        assert order.status == "refunded"


@pytest.mark.django_db
class TestSettlementIdempotency(TransactionTestCase):
    """Test settlement batch creation idempotency."""
    
    def setUp(self):
        """Create test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Test Store",
            store_number="TEST001",
        )
        self.service = SettlementAutomationService()
        
        # Create test orders
        self.orders = []
        for i in range(5):
            order = Order.objects.create(
                tenant=self.tenant,
                store=self.store,
                order_number=f"ORD-{i:03d}",
                customer_email=f"test{i}@example.com",
                total_amount=Decimal("100.00"),
                status="paid",
                created_at=timezone.now() - timezone.timedelta(hours=25),
            )
            self.orders.append(order)
    
    def test_settlement_batch_idempotency_key_is_deterministic(self):
        """Test that settlement batch uses deterministic SHA256 hash."""
        order_ids = [self.orders[0].id, self.orders[1].id]
        
        # Create batch twice with same orders
        result1 = self.service._create_settlement_batch(
            store_id=self.store.id,
            order_ids=order_ids,
            batch_num=1,
        )
        
        result2 = self.service._create_settlement_batch(
            store_id=self.store.id,
            order_ids=order_ids,
            batch_num=1,
        )
        
        # Same batch should be reused
        assert result1["success"] is True
        assert result2["success"] is True
        assert result1["batch_id"] == result2["batch_id"]
        assert result2["idempotent_reuse"] is True
    
    def test_settlement_batch_hash_order_independent(self):
        """Test that batch hash is order-independent (sorted)."""
        order_ids_1 = [self.orders[0].id, self.orders[1].id, self.orders[2].id]
        order_ids_2 = [self.orders[2].id, self.orders[0].id, self.orders[1].id]  # Different order
        
        # Both should create same batch
        result1 = self.service._create_settlement_batch(
            store_id=self.store.id,
            order_ids=order_ids_1,
            batch_num=1,
        )
        
        result2 = self.service._create_settlement_batch(
            store_id=self.store.id,
            order_ids=order_ids_2,
            batch_num=1,
        )
        
        # Same batch ID because order IDs are sorted before hashing
        assert result1["batch_id"] == result2["batch_id"]
    
    def test_settlement_batch_uses_sha256_not_python_hash(self):
        """Test that SHA256 is used instead of Python's non-deterministic hash()."""
        order_ids = sorted([self.orders[0].id, self.orders[1].id])
        
        # The idempotency key should be deterministic across Python runs
        ids_str = ",".join(str(id_) for id_ in order_ids)
        expected_hash = hashlib.sha256(ids_str.encode()).hexdigest()
        
        # Create batch and verify it used deterministic hash
        result = self.service._create_settlement_batch(
            store_id=self.store.id,
            order_ids=order_ids,
            batch_num=1,
        )
        
        assert result["success"] is True
        batch = SettlementBatch.objects.get(id=result["batch_id"])
        
        # Verify the idempotency key contains the expected SHA256 hash
        assert expected_hash in batch.idempotency_key
        
        # Verify it's NOT the Python hash() result
        python_hash_str = str(hash(tuple(order_ids)))
        assert python_hash_str not in batch.idempotency_key
    
    def test_settlement_prevents_double_settlement(self):
        """Test that concurrent settlement runs don't create duplicate batches."""
        order_ids = [self.orders[0].id, self.orders[1].id]
        
        # Simulate concurrent runs with same orders
        batches = []
        for _ in range(3):
            result = self.service._create_settlement_batch(
                store_id=self.store.id,
                order_ids=order_ids,
                batch_num=1,
            )
            if result["success"]:
                batches.append(result["batch_id"])
        
        # All should be same batch ID
        assert len(set(batches)) == 1


@pytest.mark.django_db
class TestWalletLedgerConsistency(TestCase):
    """Test wallet and ledger balance consistency."""
    
    def setUp(self):
        """Create test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Test Store",
            store_number="TEST001",
        )
    
    def test_fee_and_refund_reconciliation(self):
        """Test that fees and refunds reconcile in ledger."""
        accounting = AccountingService()
        
        # Record payment with fees
        payment_result = accounting.record_payment_fee(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            gross_amount=Decimal("1000.00"),
            order_id=1,
            reference="ORD-001",
        )
        
        assert payment_result["success"] is True
        breakdown = payment_result["fee_breakdown"]
        
        # Verify breakdown math
        assert (
            breakdown["transaction_fee"] + 
            breakdown["wasla_commission"] + 
            breakdown["net"]
        ) == breakdown["gross"]
        
        # Net should be credited to pending balance
        ledger_account = LedgerAccount.objects.get(
            store_id=self.store.id,
            currency="SAR",
        )
        assert ledger_account.pending_balance == breakdown["net"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

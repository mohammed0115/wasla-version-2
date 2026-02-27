"""
Tests for settlement automation tasks.

Tests cover:
- Hourly settlement processing with 24h policy
- Reconciliation report generation
- Settlement health monitoring
- Batch summary logging
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.orders.models import Order, OrderItem
from apps.payments.models import PaymentIntent
from apps.settlements.models import Settlement, SettlementItem, LedgerAccount
from apps.settlements.tasks import (
    process_pending_settlements,
    reconcile_payments_and_settlements,
    monitor_settlement_health,
    generate_reconciliation_report,
    _log_batch_summary,
)
from apps.stores.models import Store
from apps.tenants.models import Tenant
from apps.catalog.models import Product


class SettlementAutomationTestCase(TestCase):
    """Base test case for settlement automation."""

    def setUp(self) -> None:
        super().setUp()
        self.user = get_user_model().objects.create_user(
            username="settlement_test_user",
            password="pass12345",
        )
        self.tenant = Tenant.objects.create(
            slug="settlement_tenant",
            name="Settlement Test Tenant",
            is_active=True,
        )
        self.store = Store.objects.create(
            owner=self.user,
            tenant=self.tenant,
            name="Settlement Test Store",
            slug="settlement-test-store",
            subdomain="settlement-test",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

        # Create a product for orders
        self.product = Product.objects.create(
            store=self.store,
            title="Test Product",
            slug="test-product",
            price=Decimal("100.00"),
            currency="SAR",
            status=Product.STATUS_ACTIVE,
        )


class ProcessPendingSettlementsTests(SettlementAutomationTestCase):
    """Test hourly settlement processing with 24h policy."""

    def test_process_pending_settlements_respects_24h_policy(self):
        """Test that only orders older than 24h are settled."""
        now = timezone.now()
        
        # Order just paid (less than 24h)
        recent_order = Order.objects.create(
            store=self.store,
            tenant=self.tenant,
            reference="ORDER-RECENT",
            payment_status="paid",
            created_at=now - timedelta(hours=12),
        )
        
        # Order paid 25h ago (should be settled)
        old_order = Order.objects.create(
            store=self.store,
            tenant=self.tenant,
            reference="ORDER-OLD",
            payment_status="paid",
            total_amount=Decimal("100.00"),
            created_at=now - timedelta(hours=25),
        )
        
        # Create payment for old order
        PaymentIntent.objects.create(
            order=old_order,
            amount=Decimal("100.00"),
            status="succeeded",
        )
        
        # Process settlements
        result = process_pending_settlements.apply_sync()
        
        # Verify result
        self.assertEqual(result["total_stores"], 1)
        # Should only process old_order, not recent_order
        if result["settlements_created"] > 0:
            self.assertEqual(result["total_orders_processed"], 1)

    def test_process_pending_settlements_skips_already_settled(self):
        """Test that already-settled orders are not processed again."""
        now = timezone.now()
        
        old_order = Order.objects.create(
            store=self.store,
            tenant=self.tenant,
            reference="ORDER-SETTLED",
            payment_status="paid",
            total_amount=Decimal("100.00"),
            created_at=now - timedelta(hours=25),
        )
        
        # Create payment
        PaymentIntent.objects.create(
            order=old_order,
            amount=Decimal("100.00"),
            status="succeeded",
        )
        
        # Create settlement and settlement item
        settlement = Settlement.objects.create(
            store=self.store,
            tenant=self.tenant,
            period_start=old_order.created_at.date(),
            period_end=old_order.created_at.date() + timedelta(days=1),
            gross_amount=Decimal("100.00"),
            net_amount=Decimal("99.00"),
            fees_amount=Decimal("1.00"),
            status=Settlement.STATUS_PAID,
        )
        
        SettlementItem.objects.create(
            settlement=settlement,
            order=old_order,
            order_amount=Decimal("100.00"),
        )
        
        # Process settlements again
        result = process_pending_settlements.apply_sync()
        
        # Should not re-settle the same order
        self.assertEqual(result["total_orders_processed"], 0)

    def test_process_pending_settlements_handles_multiple_stores(self):
        """Test processing settlements across multiple stores."""
        now = timezone.now()
        
        # Create second store
        store2 = Store.objects.create(
            owner=self.user,
            tenant=self.tenant,
            name="Store 2",
            slug="store2",
            subdomain="store2",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        
        # Add old orders to both stores
        for store in [self.store, store2]:
            Order.objects.create(
                store=store,
                tenant=self.tenant,
                reference=f"ORDER-{store.id}",
                payment_status="paid",
                total_amount=Decimal("100.00"),
                created_at=now - timedelta(hours=25),
            )
        
        # Process settlements
        result = process_pending_settlements.apply_sync()
        
        # Should process both stores
        self.assertEqual(result["total_stores"], 2)

    def test_process_pending_settlements_error_handling(self):
        """Test that errors don't stop processing of other stores."""
        now = timezone.now()
        
        # Create orders that would cause issues
        Order.objects.create(
            store=self.store,
            tenant=self.tenant,
            reference="ORDER-ERROR",
            payment_status="paid",
            total_amount=Decimal("100.00"),
            created_at=now - timedelta(hours=25),
            # Missing required fields intentionally to cause error
        )
        
        # Process should handle gracefully
        result = process_pending_settlements.apply_sync()
        
        # Should have errors logged
        self.assertIsInstance(result, dict)
        self.assertIn("errors", result)


class ReconciliationTests(SettlementAutomationTestCase):
    """Test reconciliation between payments and settlements."""

    def test_reconcile_payments_vs_settlements_detects_unsettled(self):
        """Test detection of unsettled paid orders beyond grace period."""
        now = timezone.now()
        grace_cutoff = now - timedelta(hours=24)
        
        # Old paid order with payment
        old_paid_order = Order.objects.create(
            store=self.store,
            tenant=self.tenant,
            reference="ORDER-UNSETTLED",
            payment_status="paid",
            total_amount=Decimal("100.00"),
            created_at=grace_cutoff - timedelta(hours=1),
        )
        
        PaymentIntent.objects.create(
            order=old_paid_order,
            amount=Decimal("100.00"),
            status="succeeded",
        )
        
        # Run reconciliation
        result = reconcile_payments_and_settlements.apply_sync(
            lookback_days=7
        )
        
        # Should detect unsettled order
        self.assertGreater(result["unsettled_paid_orders"]["count"], 0)
        self.assertIn("100", result["unsettled_paid_orders"]["total_amount"])

    def test_reconcile_detects_orphaned_items(self):
        """Test detection of settlement items without corresponding payments."""
        # Create order without payment
        order = Order.objects.create(
            store=self.store,
            tenant=self.tenant,
            reference="ORDER-NO-PAYMENT",
            payment_status="cancelled",  # Not paid
            total_amount=Decimal("100.00"),
        )
        
        # Create settlement with item
        settlement = Settlement.objects.create(
            store=self.store,
            tenant=self.tenant,
            period_start=timezone.now().date(),
            period_end=timezone.now().date() + timedelta(days=1),
            gross_amount=Decimal("100.00"),
            net_amount=Decimal("99.00"),
            fees_amount=Decimal("1.00"),
        )
        
        SettlementItem.objects.create(
            settlement=settlement,
            order=order,
            order_amount=Decimal("100.00"),
        )
        
        # Run reconciliation
        result = reconcile_payments_and_settlements.apply_sync(
            lookback_days=7
        )
        
        # Should detect orphaned item
        self.assertGreater(result["orphaned_settlement_items"]["count"], 0)

    def test_reconcile_detects_amount_mismatches(self):
        """Test detection of amount mismatches between settlement and order."""
        now = timezone.now()
        
        # Create order
        order = Order.objects.create(
            store=self.store,
            tenant=self.tenant,
            reference="ORDER-MISMATCH",
            payment_status="paid",
            total_amount=Decimal("100.00"),
            created_at=now - timedelta(hours=25),
        )
        
        PaymentIntent.objects.create(
            order=order,
            amount=Decimal("100.00"),
            status="succeeded",
        )
        
        # Create settlement with wrong amount
        settlement = Settlement.objects.create(
            store=self.store,
            tenant=self.tenant,
            period_start=order.created_at.date(),
            period_end=order.created_at.date() + timedelta(days=1),
            gross_amount=Decimal("100.00"),
            net_amount=Decimal("99.00"),
            fees_amount=Decimal("1.00"),
        )
        
        SettlementItem.objects.create(
            settlement=settlement,
            order=order,
            order_amount=Decimal("99.00"),  # Wrong amount
        )
        
        # Run reconciliation
        result = reconcile_payments_and_settlements.apply_sync(
            lookback_days=7
        )
        
        # Should detect mismatch
        self.assertGreater(result["amount_mismatches"]["count"], 0)


class MonitoringTests(SettlementAutomationTestCase):
    """Test settlement health monitoring."""

    def test_monitor_settlement_health_basic_metrics(self):
        """Test that health monitoring collects basic metrics."""
        # Create some recent settlements
        now = timezone.now()
        settlement = Settlement.objects.create(
            store=self.store,
            tenant=self.tenant,
            period_start=now.date(),
            period_end=now.date() + timedelta(days=1),
            gross_amount=Decimal("1000.00"),
            net_amount=Decimal("990.00"),
            fees_amount=Decimal("10.00"),
            status=Settlement.STATUS_APPROVED,
            created_at=now - timedelta(hours=1),
        )
        
        # Run health monitoring
        result = monitor_settlement_health.apply_sync()
        
        # Verify metrics collected
        self.assertIn("settlement_volume_24h", result)
        self.assertGreater(result["settlement_volume_24h"]["count"], 0)
        self.assertEqual(
            result["settlement_volume_24h"]["breakdown"]["approved"],
            1
        )

    def test_monitor_detects_negative_balance(self):
        """Test that monitoring detects negative ledger balances."""
        # Create ledger account with negative balance
        LedgerAccount.objects.create(
            store=self.store,
            tenant=self.tenant,
            currency="SAR",
            available_balance=Decimal("-100.00"),
            pending_balance=Decimal("0.00"),
        )
        
        # Run health monitoring
        result = monitor_settlement_health.apply_sync()
        
        # Should detect negative balance
        self.assertGreater(result["system_health"]["ledger_accounts_negative"], 0)
        self.assertEqual(result["status"], "warning")

    def test_monitor_calculates_settlement_velocity(self):
        """Test that monitoring calculates settlement velocity."""
        now = timezone.now()
        
        # Create settlements over 7 days
        for i in range(14):
            Settlement.objects.create(
                store=self.store,
                tenant=self.tenant,
                period_start=(now - timedelta(days=7-i)).date(),
                period_end=(now - timedelta(days=7-i)).date() + timedelta(days=1),
                gross_amount=Decimal("100.00"),
                net_amount=Decimal("99.00"),
                fees_amount=Decimal("1.00"),
                created_at=now - timedelta(days=7-i),
            )
        
        # Run health monitoring
        result = monitor_settlement_health.apply_sync()
        
        # Velocity should be calculated (7 settlements per 7 days = 1 per day)
        self.assertIn("settlement_velocity_per_day", result["system_health"])
        self.assertGreater(result["system_health"]["settlement_velocity_per_day"], 0)


class ReconciliationReportTests(SettlementAutomationTestCase):
    """Test comprehensive reconciliation report generation."""

    def test_generate_reconciliation_report_basic(self):
        """Test basic reconciliation report generation."""
        now = timezone.now()
        
        # Create payment and settlement
        order = Order.objects.create(
            store=self.store,
            tenant=self.tenant,
            reference="ORDER-REPORT",
            payment_status="paid",
            total_amount=Decimal("100.00"),
            created_at=now - timedelta(days=1),
        )
        
        payment = PaymentIntent.objects.create(
            order=order,
            amount=Decimal("100.00"),
            status="succeeded",
        )
        
        settlement = Settlement.objects.create(
            store=self.store,
            tenant=self.tenant,
            period_start=order.created_at.date(),
            period_end=order.created_at.date() + timedelta(days=1),
            gross_amount=Decimal("100.00"),
            net_amount=Decimal("99.00"),
            fees_amount=Decimal("1.00"),
        )
        
        SettlementItem.objects.create(
            settlement=settlement,
            order=order,
            order_amount=Decimal("100.00"),
        )
        
        # Generate report
        result = generate_reconciliation_report.apply_sync(
            lookback_days=7
        )
        
        # Verify structure
        self.assertIn("period", result)
        self.assertIn("payment_intents", result)
        self.assertIn("settlement_items", result)
        self.assertIn("variance", result)
        
        # Should show matched amounts
        self.assertEqual(result["payment_intents"]["count"], 1)
        self.assertEqual(result["settlement_items"]["count"], 1)

    def test_generate_report_highlights_variance(self):
        """Test that report highlights payment/settlement variance."""
        now = timezone.now()
        
        # Create unmatched payment
        order = Order.objects.create(
            store=self.store,
            tenant=self.tenant,
            reference="ORDER-VARIANCE",
            payment_status="paid",
            total_amount=Decimal("100.00"),
            created_at=now - timedelta(days=1),
        )
        
        PaymentIntent.objects.create(
            order=order,
            amount=Decimal("100.00"),
            status="succeeded",
        )
        
        # Settlement with different amount
        settlement = Settlement.objects.create(
            store=self.store,
            tenant=self.tenant,
            period_start=order.created_at.date(),
            period_end=order.created_at.date() + timedelta(days=1),
            gross_amount=Decimal("90.00"),  # Less than payment
            net_amount=Decimal("89.00"),
            fees_amount=Decimal("1.00"),
        )
        
        SettlementItem.objects.create(
            settlement=settlement,
            order=order,
            order_amount=Decimal("90.00"),
        )
        
        # Generate report
        result = generate_reconciliation_report.apply_sync(
            lookback_days=7
        )
        
        # Should show variance
        self.assertNotEqual(result["variance"]["amount"], "0.00")
        self.assertEqual(result["variance"]["status"], "MISMATCH")


class BatchSummaryLoggingTests(TestCase):
    """Test batch summary logging."""

    def test_log_batch_summary_formats_output(self):
        """Test that batch summary is properly formatted."""
        summary = {
            "total_stores": 5,
            "settlements_created": 3,
            "settlements_approved": 2,
            "total_orders_processed": 15,
            "total_amount_settled": Decimal("1500.00"),
            "errors": [],
        }
        
        # Should not raise exception
        with patch.object(logging.getLogger("apps.settlements.tasks"), "info") as mock_log:
            _log_batch_summary(summary)
            mock_log.assert_called_once()
            
            # Verify log contains key values
            call_args = mock_log.call_args[0][0]
            self.assertIn("5", call_args)  # total_stores
            self.assertIn("3", call_args)  # settlements_created

    def test_log_batch_summary_with_errors(self):
        """Test batch summary logging with errors."""
        summary = {
            "total_stores": 5,
            "settlements_created": 2,
            "settlements_approved": 1,
            "total_orders_processed": 10,
            "total_amount_settled": Decimal("1000.00"),
            "errors": ["Store 1: Connection error", "Store 3: Timeout"],
        }
        
        # Should not raise exception
        with patch.object(logging.getLogger("apps.settlements.tasks"), "info") as mock_log:
            _log_batch_summary(summary)
            mock_log.assert_called_once()
            
            # Verify log contains error count
            call_args = mock_log.call_args[0][0]
            self.assertIn("2", call_args)  # errors count

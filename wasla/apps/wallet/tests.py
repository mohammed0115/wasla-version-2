from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from apps.stores.models import Store
from apps.tenants.models import Tenant
from apps.wallet.models import Wallet, WithdrawalRequest, WalletTransaction
from apps.wallet.services.wallet_service import WalletService


class WalletOperationalAccountingServiceTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        owner = get_user_model().objects.create_user(username="wallet-owner", password="pass12345")
        self.tenant = Tenant.objects.create(slug="tenant-wallet", name="Tenant Wallet", is_active=True)
        self.store = Store.objects.create(
            owner=owner,
            tenant=self.tenant,
            name="Wallet Store",
            slug="wallet-store",
            subdomain="wallet-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

    def test_order_paid_and_delivered_move_pending_to_available(self):
        wallet = WalletService.on_order_paid(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            net_amount=Decimal("80.00"),
            reference="order_paid:1",
        )
        wallet.refresh_from_db()
        self.assertEqual(str(wallet.pending_balance), "80.00")
        self.assertEqual(str(wallet.available_balance), "0.00")

        WalletService.on_order_delivered(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            net_amount=Decimal("80.00"),
            reference="order_delivered:1",
        )
        wallet.refresh_from_db()
        self.assertEqual(str(wallet.pending_balance), "0.00")
        self.assertEqual(str(wallet.available_balance), "80.00")
        self.assertEqual(str(wallet.balance), "80.00")

    def test_refund_deducts_pending_then_available(self):
        wallet = WalletService.get_or_create_wallet(store_id=self.store.id, tenant_id=self.tenant.id)
        wallet.pending_balance = Decimal("30.00")
        wallet.available_balance = Decimal("40.00")
        wallet.balance = Decimal("70.00")
        wallet.save(update_fields=["pending_balance", "available_balance", "balance"])

        WalletService.on_refund(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("50.00"),
            reference="refund:1",
        )
        wallet.refresh_from_db()
        self.assertEqual(str(wallet.pending_balance), "0.00")
        self.assertEqual(str(wallet.available_balance), "20.00")
        self.assertEqual(str(wallet.balance), "20.00")

    def test_prevent_withdrawal_above_available(self):
        wallet = WalletService.get_or_create_wallet(store_id=self.store.id, tenant_id=self.tenant.id)
        wallet.available_balance = Decimal("10.00")
        wallet.balance = Decimal("10.00")
        wallet.save(update_fields=["available_balance", "balance"])

        with self.assertRaisesMessage(ValueError, "Withdrawal amount exceeds available balance"):
            WalletService.create_withdrawal_request(
                store_id=self.store.id,
                tenant_id=self.tenant.id,
                amount=Decimal("11.00"),
            )

    def test_ledger_integrity_check(self):
        wallet = WalletService.get_or_create_wallet(store_id=self.store.id, tenant_id=self.tenant.id)
        WalletService.credit(wallet, Decimal("10.00"), "manual-topup")
        WalletService.on_order_paid(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            net_amount=Decimal("15.00"),
            reference="order_paid:200",
        )

        wallet.refresh_from_db()
        result = WalletService.ledger_integrity_check(store_id=self.store.id, tenant_id=self.tenant.id)
        self.assertTrue(result["is_valid"])


class WithdrawalReferenceCodeTests(TestCase):
    """Test withdrawal reference code generation and uniqueness."""
    
    def setUp(self) -> None:
        super().setUp()
        owner = get_user_model().objects.create_user(username="owner-ref", password="pass12345")
        self.tenant = Tenant.objects.create(slug="tenant-ref", name="Tenant Ref", is_active=True)
        self.store = Store.objects.create(
            owner=owner,
            tenant=self.tenant,
            name="Ref Store",
            slug="ref-store",
            subdomain="ref-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

    def test_withdrawal_request_generates_reference_code(self):
        """Test that withdrawal request generates a reference code automatically."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            currency="USD"
        )
        wallet.available_balance = Decimal("100.00")
        wallet.balance = Decimal("100.00")
        wallet.save(update_fields=["available_balance", "balance"])

        withdrawal = WalletService.create_withdrawal_request(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("50.00"),
        )

        self.assertIsNotNone(withdrawal.reference_code)
        self.assertIn(f"WD-{self.store.id}", withdrawal.reference_code)

    def test_withdrawal_with_custom_reference_code(self):
        """Test that a custom reference code can be provided."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )
        wallet.available_balance = Decimal("100.00")
        wallet.balance = Decimal("100.00")
        wallet.save(update_fields=["available_balance", "balance"])

        custom_ref = "CUSTOM-REF-123"
        withdrawal = WalletService.create_withdrawal_request(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("50.00"),
            reference_code=custom_ref,
        )

        self.assertEqual(withdrawal.reference_code, custom_ref)

    def test_get_withdrawal_request_by_reference(self):
        """Test retrieving withdrawal by reference code."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )
        wallet.available_balance = Decimal("100.00")
        wallet.balance = Decimal("100.00")
        wallet.save(update_fields=["available_balance", "balance"])

        withdrawal = WalletService.create_withdrawal_request(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("50.00"),
        )

        found = WalletService.get_withdrawal_request_by_reference(
            reference_code=withdrawal.reference_code
        )

        self.assertEqual(found.id, withdrawal.id)


class WithdrawalLifecycleTests(TestCase):
    """Test complete withdrawal request lifecycle: pending -> approved -> paid."""

    def setUp(self) -> None:
        super().setUp()
        owner = get_user_model().objects.create_user(username="owner-lifecycle", password="pass12345")
        self.tenant = Tenant.objects.create(slug="tenant-lifecycle", name="Tenant Lifecycle", is_active=True)
        self.store = Store.objects.create(
            owner=owner,
            tenant=self.tenant,
            name="Lifecycle Store",
            slug="lifecycle-store",
            subdomain="lifecycle-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        self.admin_user = get_user_model().objects.create_user(
            username="admin-lifecycle",
            password="pass12345",
            is_staff=True
        )

    def test_withdrawal_pending_to_approved_to_paid(self):
        """Test full withdrawal lifecycle: pending -> approved -> paid."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )
        wallet.available_balance = Decimal("100.00")
        wallet.balance = Decimal("100.00")
        wallet.save(update_fields=["available_balance", "balance"])

        # Create withdrawal request
        withdrawal = WalletService.create_withdrawal_request(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("50.00"),
        )
        self.assertEqual(withdrawal.status, WithdrawalRequest.STATUS_PENDING)
        self.assertIsNone(withdrawal.processed_at)

        # Approve withdrawal
        approved = WalletService.approve_withdrawal(
            withdrawal_id=withdrawal.id,
            actor_user_id=self.admin_user.id,
        )
        self.assertEqual(approved.status, WithdrawalRequest.STATUS_APPROVED)
        self.assertEqual(approved.processed_by_user_id, self.admin_user.id)
        self.assertIsNotNone(approved.processed_at)

        # Mark as paid
        paid = WalletService.mark_withdrawal_paid(
            withdrawal_id=withdrawal.id,
            actor_user_id=self.admin_user.id,
        )
        self.assertEqual(paid.status, WithdrawalRequest.STATUS_PAID)

        # Verify wallet balance decreased
        wallet.refresh_from_db()
        self.assertEqual(str(wallet.available_balance), "50.00")
        self.assertEqual(str(wallet.balance), "50.00")

    def test_rejection_flow(self):
        """Test withdrawal rejection."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )
        wallet.available_balance = Decimal("100.00")
        wallet.balance = Decimal("100.00")
        wallet.save(update_fields=["available_balance", "balance"])

        withdrawal = WalletService.create_withdrawal_request(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("50.00"),
        )

        # Reject withdrawal
        rejected = WalletService.reject_withdrawal(
            withdrawal_id=withdrawal.id,
            actor_user_id=self.admin_user.id,
            note="Insufficient documentation",
        )
        self.assertEqual(rejected.status, WithdrawalRequest.STATUS_REJECTED)
        self.assertIn("Insufficient documentation", rejected.note)

        # Wallet balance should remain unchanged
        wallet.refresh_from_db()
        self.assertEqual(str(wallet.available_balance), "100.00")

    def test_cannot_approve_twice(self):
        """Test that withdrawal cannot be approved twice."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )
        wallet.available_balance = Decimal("100.00")
        wallet.balance = Decimal("100.00")
        wallet.save(update_fields=["available_balance", "balance"])

        withdrawal = WalletService.create_withdrawal_request(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("50.00"),
        )

        # First approval
        WalletService.approve_withdrawal(
            withdrawal_id=withdrawal.id,
            actor_user_id=self.admin_user.id,
        )

        # Second approval should fail
        with self.assertRaisesMessage(ValueError, "Only pending withdrawal can be approved"):
            WalletService.approve_withdrawal(
                withdrawal_id=withdrawal.id,
                actor_user_id=self.admin_user.id,
            )


class WithdrawalEdgeCaseTests(TestCase):
    """Test edge cases and error conditions in withdrawal handling."""

    def setUp(self) -> None:
        super().setUp()
        owner = get_user_model().objects.create_user(username="owner-edge", password="pass12345")
        self.tenant = Tenant.objects.create(slug="tenant-edge", name="Tenant Edge", is_active=True)
        self.store = Store.objects.create(
            owner=owner,
            tenant=self.tenant,
            name="Edge Store",
            slug="edge-store",
            subdomain="edge-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

    def test_withdrawal_amount_must_be_positive(self):
        """Test that withdrawal amount must be positive."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )

        with self.assertRaisesMessage(ValueError, "Amount must be positive"):
            WalletService.create_withdrawal_request(
                store_id=self.store.id,
                tenant_id=self.tenant.id,
                amount=Decimal("0.00"),
            )

        with self.assertRaisesMessage(ValueError, "Amount must be positive"):
            WalletService.create_withdrawal_request(
                store_id=self.store.id,
                tenant_id=self.tenant.id,
                amount=Decimal("-10.00"),
            )

    def test_cannot_withdraw_if_balance_insufficient(self):
        """Test that withdrawal fails if available balance is insufficient."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )
        wallet.available_balance = Decimal("50.00")
        wallet.balance = Decimal("50.00")
        wallet.save(update_fields=["available_balance", "balance"])

        with self.assertRaisesMessage(ValueError, "Withdrawal amount exceeds available balance"):
            WalletService.create_withdrawal_request(
                store_id=self.store.id,
                tenant_id=self.tenant.id,
                amount=Decimal("60.00"),
            )

    def test_cannot_approve_if_balance_changed(self):
        """Test that approval fails if balance drops before approval."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )
        wallet.available_balance = Decimal("100.00")
        wallet.balance = Decimal("100.00")
        wallet.save(update_fields=["available_balance", "balance"])

        withdrawal = WalletService.create_withdrawal_request(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("90.00"),
        )

        # Manually reduce available balance
        wallet.available_balance = Decimal("50.00")
        wallet.balance = Decimal("50.00")
        wallet.save(update_fields=["available_balance", "balance"])

        # Approval should fail
        with self.assertRaisesMessage(ValueError, "Withdrawal amount exceeds available balance"):
            WalletService.approve_withdrawal(
                withdrawal_id=withdrawal.id,
                actor_user_id=None,
            )

    def test_multiple_pending_withdrawals_counted_in_summary(self):
        """Test that multiple pending withdrawals are reflected in wallet summary."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )
        wallet.available_balance = Decimal("200.00")
        wallet.balance = Decimal("200.00")
        wallet.save(update_fields=["available_balance", "balance"])

        # Create multiple withdrawals
        wd1 = WalletService.create_withdrawal_request(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("50.00"),
        )
        wd2 = WalletService.create_withdrawal_request(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("30.00"),
        )

        summary = WalletService.get_wallet_summary(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )

        self.assertEqual(summary["available_balance"], "200.00")
        self.assertEqual(summary["pending_withdrawal_amount"], "80.00")
        self.assertEqual(summary["effective_available_balance"], "120.00")


class LedgerIntegrityTests(TestCase):
    """Test ledger integrity validation and transaction tracking."""

    def setUp(self) -> None:
        super().setUp()
        owner = get_user_model().objects.create_user(username="owner-ledger", password="pass12345")
        self.tenant = Tenant.objects.create(slug="tenant-ledger", name="Tenant Ledger", is_active=True)
        self.store = Store.objects.create(
            owner=owner,
            tenant=self.tenant,
            name="Ledger Store",
            slug="ledger-store",
            subdomain="ledger-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

    def test_complex_transaction_sequence_integrity(self):
        """Test ledger integrity across complex transaction sequences."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )

        # Sequence: order paid -> credit -> order delivered -> refund
        WalletService.on_order_paid(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            net_amount=Decimal("100.00"),
            reference="order:1",
        )

        WalletService.credit(
            wallet,
            Decimal("50.00"),
            "manual-topup:1"
        )

        WalletService.on_order_delivered(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            net_amount=Decimal("100.00"),
            reference="order:1-delivered",
        )

        WalletService.on_refund(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("30.00"),
            reference="refund:1",
        )

        # Verify ledger integrity
        result = WalletService.ledger_integrity_check(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )

        self.assertTrue(result["is_valid"])
        wallet.refresh_from_db()
        self.assertEqual(str(wallet.available_balance), "120.00")
        self.assertEqual(str(wallet.pending_balance), "0.00")
        self.assertEqual(str(wallet.balance), "120.00")

    def test_idempotent_order_paid_events(self):
        """Test that duplicate order_paid events don't double-credit."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )

        # Pay order twice with same reference
        WalletService.on_order_paid(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            net_amount=Decimal("100.00"),
            reference="order:idempotent",
        )

        wallet.refresh_from_db()
        balance_after_first = wallet.pending_balance

        # Second call with same reference
        WalletService.on_order_paid(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            net_amount=Decimal("100.00"),
            reference="order:idempotent",
        )

        wallet.refresh_from_db()
        balance_after_second = wallet.pending_balance

        # Balances should be identical (idempotent)
        self.assertEqual(balance_after_first, balance_after_second)


class WalletSummaryTests(TestCase):
    """Test wallet summary reporting with active and pending amounts."""

    def setUp(self) -> None:
        super().setUp()
        owner = get_user_model().objects.create_user(username="owner-summary", password="pass12345")
        self.tenant = Tenant.objects.create(slug="tenant-summary", name="Tenant Summary", is_active=True)
        self.store = Store.objects.create(
            owner=owner,
            tenant=self.tenant,
            name="Summary Store",
            slug="summary-store",
            subdomain="summary-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

    def test_wallet_summary_includes_pending_and_available(self):
        """Test that wallet summary includes both pending and available balances."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            currency="SAR",
        )
        wallet.available_balance = Decimal("500.00")
        wallet.pending_balance = Decimal("200.00")
        wallet.balance = Decimal("700.00")
        wallet.save(update_fields=["available_balance", "pending_balance", "balance"])

        summary = WalletService.get_wallet_summary(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )

        self.assertEqual(summary["available_balance"], "500.00")
        self.assertEqual(summary["pending_balance"], "200.00")
        self.assertEqual(summary["balance"], "700.00")
        self.assertEqual(summary["currency"], "SAR")
        self.assertTrue(summary["is_active"])


class TransactionListingTests(TestCase):
    """Test transaction listing and filtering."""

    def setUp(self) -> None:
        super().setUp()
        owner = get_user_model().objects.create_user(username="owner-listing", password="pass12345")
        self.tenant = Tenant.objects.create(slug="tenant-listing", name="Tenant Listing", is_active=True)
        self.store = Store.objects.create(
            owner=owner,
            tenant=self.tenant,
            name="Listing Store",
            slug="listing-store",
            subdomain="listing-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

    def test_list_wallet_transactions(self):
        """Test listing wallet transactions."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )

        # Create various transactions
        WalletService.credit(wallet, Decimal("100.00"), "credit:1")
        WalletService.on_order_paid(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            net_amount=Decimal("50.00"),
            reference="order:1",
        )

        transactions = WalletService.list_wallet_transactions(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )

        self.assertGreater(len(transactions), 0)
        self.assertTrue(all(isinstance(t, WalletTransaction) for t in transactions))

    def test_list_transactions_filtered_by_event_type(self):
        """Test filtering transactions by event type."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )

        WalletService.credit(wallet, Decimal("100.00"), "credit:1")
        WalletService.on_order_paid(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            net_amount=Decimal("50.00"),
            reference="order:1",
        )

        order_txns = WalletService.list_wallet_transactions(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            event_type="order_paid",
        )

        self.assertTrue(all(t.event_type == "order_paid" for t in order_txns))

    def test_list_withdrawal_requests(self):
        """Test listing withdrawal requests."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )
        wallet.available_balance = Decimal("200.00")
        wallet.balance = Decimal("200.00")
        wallet.save(update_fields=["available_balance", "balance"])

        # Create withdrawals
        WalletService.create_withdrawal_request(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("50.00"),
        )
        WalletService.create_withdrawal_request(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("60.00"),
        )

        withdrawals = WalletService.list_withdrawal_requests(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )

        self.assertEqual(len(withdrawals), 2)

    def test_list_withdrawals_filtered_by_status(self):
        """Test filtering withdrawal requests by status."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )
        wallet.available_balance = Decimal("200.00")
        wallet.balance = Decimal("200.00")
        wallet.save(update_fields=["available_balance", "balance"])

        admin_user = get_user_model().objects.create_user(
            username="admin-list",
            password="pass12345",
            is_staff=True
        )

        # Create and approve one withdrawal
        wd1 = WalletService.create_withdrawal_request(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("50.00"),
        )
        WalletService.approve_withdrawal(
            withdrawal_id=wd1.id,
            actor_user_id=admin_user.id,
        )

        # Keep one pending
        WalletService.create_withdrawal_request(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("60.00"),
        )

        pending = WalletService.list_withdrawal_requests(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            status=WithdrawalRequest.STATUS_PENDING,
        )

        self.assertEqual(len(pending), 1)


class RefundEdgeCaseTests(TestCase):
    """Test refund handling with various balance states."""

    def setUp(self) -> None:
        super().setUp()
        owner = get_user_model().objects.create_user(username="owner-refund", password="pass12345")
        self.tenant = Tenant.objects.create(slug="tenant-refund", name="Tenant Refund", is_active=True)
        self.store = Store.objects.create(
            owner=owner,
            tenant=self.tenant,
            name="Refund Store",
            slug="refund-store",
            subdomain="refund-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

    def test_refund_only_from_pending(self):
        """Test refund that only affects pending balance."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )
        wallet.pending_balance = Decimal("100.00")
        wallet.available_balance = Decimal("0.00")
        wallet.balance = Decimal("100.00")
        wallet.save(update_fields=["pending_balance", "available_balance", "balance"])

        WalletService.on_refund(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("50.00"),
            reference="refund:pending_only",
        )

        wallet.refresh_from_db()
        self.assertEqual(str(wallet.pending_balance), "50.00")
        self.assertEqual(str(wallet.available_balance), "0.00")

    def test_refund_only_from_available(self):
        """Test refund that only affects available balance."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )
        wallet.pending_balance = Decimal("0.00")
        wallet.available_balance = Decimal("100.00")
        wallet.balance = Decimal("100.00")
        wallet.save(update_fields=["pending_balance", "available_balance", "balance"])

        WalletService.on_refund(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            amount=Decimal("50.00"),
            reference="refund:available_only",
        )

        wallet.refresh_from_db()
        self.assertEqual(str(wallet.pending_balance), "0.00")
        self.assertEqual(str(wallet.available_balance), "50.00")

    def test_refund_insufficient_balance_fails(self):
        """Test that refund fails if total balance is insufficient."""
        wallet = WalletService.get_or_create_wallet(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
        )
        wallet.pending_balance = Decimal("30.00")
        wallet.available_balance = Decimal("40.00")
        wallet.balance = Decimal("70.00")
        wallet.save(update_fields=["pending_balance", "available_balance", "balance"])

        with self.assertRaisesMessage(ValueError, "Insufficient balance for refund"):
            WalletService.on_refund(
                store_id=self.store.id,
                tenant_id=self.tenant.id,
                amount=Decimal("100.00"),
                reference="refund:fail",
            )


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", ".localhost"])
class WalletAdminWithdrawalAPITests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        User = get_user_model()
        self.staff = User.objects.create_user(username="wallet-admin", password="pass12345", is_staff=True)
        owner = User.objects.create_user(username="wallet-owner-api", password="pass12345")
        self.tenant = Tenant.objects.create(slug="tenant-wallet-api", name="Tenant Wallet API", is_active=True)
        self.store = Store.objects.create(
            owner=owner,
            tenant=self.tenant,
            name="Wallet API Store",
            slug="wallet-api-store",
            subdomain="wallet-api-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

        self.wallet = Wallet.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            available_balance=Decimal("100.00"),
            pending_balance=Decimal("0.00"),
            balance=Decimal("100.00"),
            currency="USD",
            is_active=True,
        )
        self.withdrawal = WithdrawalRequest.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            wallet=self.wallet,
            amount=Decimal("30.00"),
            reference_code="WD-TEST-001",
        )

    def test_admin_approve_and_mark_paid(self):
        self.client.force_login(self.staff)

        approve = self.client.post(f"/api/admin/wallet/withdrawals/{self.withdrawal.id}/approve/")
        self.assertEqual(approve.status_code, 200)

        paid = self.client.post(f"/api/admin/wallet/withdrawals/{self.withdrawal.id}/paid/")
        self.assertEqual(paid.status_code, 200)

        self.withdrawal.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(self.withdrawal.status, WithdrawalRequest.STATUS_PAID)
        self.assertEqual(str(self.wallet.available_balance), "70.00")
        self.assertEqual(str(self.wallet.balance), "70.00")


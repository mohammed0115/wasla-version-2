
import uuid
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from ..models import Wallet, WalletTransaction, WithdrawalRequest
from apps.stores.models import Store


class WalletService:

    @staticmethod
    def _to_decimal(amount: Decimal | str | int | float) -> Decimal:
        value = Decimal(str(amount or "0"))
        return value.quantize(Decimal("0.01"))

    @staticmethod
    def _ensure_non_negative(*, available_balance: Decimal, pending_balance: Decimal) -> None:
        if available_balance < Decimal("0") or pending_balance < Decimal("0"):
            raise ValueError("Balance cannot be negative")

    @staticmethod
    def _sync_total_balance(wallet: Wallet) -> None:
        wallet.balance = WalletService._to_decimal(wallet.available_balance + wallet.pending_balance)

    @staticmethod
    def _record_transaction(
        *,
        wallet: Wallet,
        transaction_type: str,
        balance_bucket: str,
        event_type: str,
        amount: Decimal,
        reference: str,
        metadata_json: dict | None = None,
    ) -> WalletTransaction:
        return WalletTransaction.objects.create(
            tenant_id=wallet.tenant_id,
            wallet=wallet,
            transaction_type=transaction_type,
            balance_bucket=balance_bucket,
            event_type=event_type,
            amount=WalletService._to_decimal(amount),
            reference=reference,
            metadata_json=metadata_json or {},
        )

    @staticmethod
    def get_or_create_wallet(store_id, currency="USD", tenant_id=None):
        resolved_tenant_id = tenant_id
        if resolved_tenant_id is None:
            resolved_tenant_id = (
                Store.objects.filter(id=store_id)
                .values_list("tenant_id", flat=True)
                .first()
            )
        wallet, _ = Wallet.objects.get_or_create(
            store_id=store_id,
            defaults={
                "tenant_id": resolved_tenant_id,
                "currency": currency,
                "balance": Decimal("0"),
                "available_balance": Decimal("0"),
                "pending_balance": Decimal("0"),
            },
        )

        updates = []
        if wallet.tenant_id != resolved_tenant_id:
            wallet.tenant_id = resolved_tenant_id
            updates.append("tenant_id")
        if wallet.currency != currency:
            wallet.currency = currency
            updates.append("currency")

        if updates:
            wallet.save(update_fields=updates)

        if wallet.balance != WalletService._to_decimal(wallet.available_balance + wallet.pending_balance):
            WalletService._sync_total_balance(wallet)
            wallet.save(update_fields=["balance"])

        return wallet

    @staticmethod
    @transaction.atomic
    def credit(wallet, amount: Decimal, reference: str):
        if amount <= 0:
            raise ValueError("Amount must be positive")

        amount = WalletService._to_decimal(amount)

        WalletService._record_transaction(
            wallet=wallet,
            transaction_type="credit",
            balance_bucket="available",
            event_type="adjustment",
            amount=amount,
            reference=reference,
        )

        wallet.available_balance = WalletService._to_decimal(wallet.available_balance + amount)
        WalletService._sync_total_balance(wallet)
        wallet.save(update_fields=["available_balance", "balance"])

    @staticmethod
    @transaction.atomic
    def debit(wallet, amount: Decimal, reference: str):
        amount = WalletService._to_decimal(amount)
        if wallet.available_balance < amount:
            raise ValueError("Insufficient balance")

        WalletService._record_transaction(
            wallet=wallet,
            transaction_type="debit",
            balance_bucket="available",
            event_type="adjustment",
            amount=amount,
            reference=reference,
        )

        wallet.available_balance = WalletService._to_decimal(wallet.available_balance - amount)
        WalletService._sync_total_balance(wallet)
        wallet.save(update_fields=["available_balance", "balance"])

    @staticmethod
    @transaction.atomic
    def on_order_paid(*, store_id: int, net_amount: Decimal, reference: str, tenant_id: int | None = None) -> Wallet:
        amount = WalletService._to_decimal(net_amount)
        if amount <= 0:
            raise ValueError("Amount must be positive")

        wallet = WalletService.get_or_create_wallet(store_id=store_id, tenant_id=tenant_id)
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

        if wallet.transactions.filter(event_type="order_paid", reference=reference).exists():
            return wallet

        WalletService._record_transaction(
            wallet=wallet,
            transaction_type="credit",
            balance_bucket="pending",
            event_type="order_paid",
            amount=amount,
            reference=reference,
        )

        wallet.pending_balance = WalletService._to_decimal(wallet.pending_balance + amount)
        WalletService._sync_total_balance(wallet)
        wallet.save(update_fields=["pending_balance", "balance"])
        return wallet

    @staticmethod
    @transaction.atomic
    def on_order_delivered(*, store_id: int, net_amount: Decimal, reference: str, tenant_id: int | None = None) -> Wallet:
        amount = WalletService._to_decimal(net_amount)
        if amount <= 0:
            raise ValueError("Amount must be positive")

        wallet = WalletService.get_or_create_wallet(store_id=store_id, tenant_id=tenant_id)
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

        if wallet.transactions.filter(event_type="order_delivered", reference=reference).exists():
            return wallet

        releasable_amount = min(wallet.pending_balance, amount)
        if releasable_amount <= 0:
            return wallet

        WalletService._record_transaction(
            wallet=wallet,
            transaction_type="debit",
            balance_bucket="pending",
            event_type="order_delivered",
            amount=releasable_amount,
            reference=reference,
            metadata_json={"phase": "release_pending"},
        )
        WalletService._record_transaction(
            wallet=wallet,
            transaction_type="credit",
            balance_bucket="available",
            event_type="order_delivered",
            amount=releasable_amount,
            reference=reference,
            metadata_json={"phase": "release_available"},
        )

        wallet.pending_balance = WalletService._to_decimal(wallet.pending_balance - releasable_amount)
        wallet.available_balance = WalletService._to_decimal(wallet.available_balance + releasable_amount)
        WalletService._sync_total_balance(wallet)
        wallet.save(update_fields=["pending_balance", "available_balance", "balance"])
        return wallet

    @staticmethod
    @transaction.atomic
    def on_refund(*, store_id: int, amount: Decimal, reference: str, tenant_id: int | None = None) -> Wallet:
        refund_amount = WalletService._to_decimal(amount)
        if refund_amount <= 0:
            raise ValueError("Amount must be positive")

        wallet = WalletService.get_or_create_wallet(store_id=store_id, tenant_id=tenant_id)
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

        if wallet.transactions.filter(event_type="refund", reference=reference).exists():
            return wallet

        pending_deduction = min(wallet.pending_balance, refund_amount)
        available_deduction = WalletService._to_decimal(refund_amount - pending_deduction)
        if available_deduction > wallet.available_balance:
            raise ValueError("Insufficient balance for refund")

        if pending_deduction > 0:
            WalletService._record_transaction(
                wallet=wallet,
                transaction_type="debit",
                balance_bucket="pending",
                event_type="refund",
                amount=pending_deduction,
                reference=reference,
            )
            wallet.pending_balance = WalletService._to_decimal(wallet.pending_balance - pending_deduction)

        if available_deduction > 0:
            WalletService._record_transaction(
                wallet=wallet,
                transaction_type="debit",
                balance_bucket="available",
                event_type="refund",
                amount=available_deduction,
                reference=reference,
            )
            wallet.available_balance = WalletService._to_decimal(wallet.available_balance - available_deduction)

        WalletService._sync_total_balance(wallet)
        WalletService._ensure_non_negative(
            available_balance=wallet.available_balance,
            pending_balance=wallet.pending_balance,
        )
        wallet.save(update_fields=["pending_balance", "available_balance", "balance"])
        return wallet

    @staticmethod
    def _generate_reference_code(store_id: int) -> str:
        """Generate unique withdrawal reference code: WD-{store_id}-{uuid}."""
        return f"WD-{store_id}-{uuid.uuid4().hex[:12].upper()}"

    @staticmethod
    @transaction.atomic
    def create_withdrawal_request(
        *,
        store_id: int,
        amount: Decimal,
        tenant_id: int | None = None,
        note: str = "",
        reference_code: str | None = None,
    ) -> WithdrawalRequest:
        request_amount = WalletService._to_decimal(amount)
        if request_amount <= 0:
            raise ValueError("Amount must be positive")

        wallet = WalletService.get_or_create_wallet(store_id=store_id, tenant_id=tenant_id)
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

        if request_amount > wallet.available_balance:
            raise ValueError("Withdrawal amount exceeds available balance")

        if reference_code is None:
            reference_code = WalletService._generate_reference_code(store_id)

        return WithdrawalRequest.objects.create(
            tenant_id=wallet.tenant_id,
            store_id=wallet.store_id,
            wallet=wallet,
            amount=request_amount,
            status=WithdrawalRequest.STATUS_PENDING,
            reference_code=reference_code,
            note=note,
        )

    @staticmethod
    @transaction.atomic
    def approve_withdrawal(*, withdrawal_id: int, actor_user_id: int | None = None) -> WithdrawalRequest:
        withdrawal = WithdrawalRequest.objects.select_for_update().select_related("wallet").filter(id=withdrawal_id).first()
        if not withdrawal:
            raise ValueError("Withdrawal request not found")
        if withdrawal.status != WithdrawalRequest.STATUS_PENDING:
            raise ValueError("Only pending withdrawal can be approved")

        wallet = Wallet.objects.select_for_update().get(pk=withdrawal.wallet_id)
        if withdrawal.amount > wallet.available_balance:
            raise ValueError("Withdrawal amount exceeds available balance")

        withdrawal.status = WithdrawalRequest.STATUS_APPROVED
        withdrawal.processed_at = timezone.now()
        withdrawal.processed_by_user_id = actor_user_id
        withdrawal.save(update_fields=["status", "processed_at", "processed_by_user_id"])
        return withdrawal

    @staticmethod
    @transaction.atomic
    def reject_withdrawal(*, withdrawal_id: int, actor_user_id: int | None = None, note: str = "") -> WithdrawalRequest:
        withdrawal = WithdrawalRequest.objects.select_for_update().filter(id=withdrawal_id).first()
        if not withdrawal:
            raise ValueError("Withdrawal request not found")
        if withdrawal.status != WithdrawalRequest.STATUS_PENDING:
            raise ValueError("Only pending withdrawal can be rejected")

        withdrawal.status = WithdrawalRequest.STATUS_REJECTED
        withdrawal.processed_at = timezone.now()
        withdrawal.processed_by_user_id = actor_user_id
        if note:
            withdrawal.note = note
        withdrawal.save(update_fields=["status", "processed_at", "processed_by_user_id", "note"])
        return withdrawal

    @staticmethod
    @transaction.atomic
    def mark_withdrawal_paid(*, withdrawal_id: int, actor_user_id: int | None = None) -> WithdrawalRequest:
        withdrawal = WithdrawalRequest.objects.select_for_update().select_related("wallet").filter(id=withdrawal_id).first()
        if not withdrawal:
            raise ValueError("Withdrawal request not found")
        if withdrawal.status != WithdrawalRequest.STATUS_APPROVED:
            raise ValueError("Only approved withdrawal can be marked as paid")

        wallet = Wallet.objects.select_for_update().get(pk=withdrawal.wallet_id)
        if withdrawal.amount > wallet.available_balance:
            raise ValueError("Withdrawal amount exceeds available balance")

        WalletService._record_transaction(
            wallet=wallet,
            transaction_type="debit",
            balance_bucket="available",
            event_type="withdrawal",
            amount=withdrawal.amount,
            reference=f"withdrawal:{withdrawal.id}",
        )

        wallet.available_balance = WalletService._to_decimal(wallet.available_balance - withdrawal.amount)
        WalletService._sync_total_balance(wallet)
        WalletService._ensure_non_negative(
            available_balance=wallet.available_balance,
            pending_balance=wallet.pending_balance,
        )
        wallet.save(update_fields=["available_balance", "balance"])

        withdrawal.status = WithdrawalRequest.STATUS_PAID
        withdrawal.processed_at = timezone.now()
        withdrawal.processed_by_user_id = actor_user_id
        withdrawal.save(update_fields=["status", "processed_at", "processed_by_user_id"])
        return withdrawal

    @staticmethod
    def ledger_integrity_check(*, store_id: int, tenant_id: int | None = None) -> dict:
        wallet = WalletService.get_or_create_wallet(store_id=store_id, tenant_id=tenant_id)
        txns = WalletTransaction.objects.filter(wallet=wallet).order_by("created_at", "id")

        available = Decimal("0.00")
        pending = Decimal("0.00")
        for txn in txns:
            sign = Decimal("1") if txn.transaction_type == "credit" else Decimal("-1")
            amount = WalletService._to_decimal(txn.amount)
            if txn.balance_bucket == "pending":
                pending = WalletService._to_decimal(pending + sign * amount)
            else:
                available = WalletService._to_decimal(available + sign * amount)

        total = WalletService._to_decimal(available + pending)
        expected_available = WalletService._to_decimal(wallet.available_balance)
        expected_pending = WalletService._to_decimal(wallet.pending_balance)
        expected_total = WalletService._to_decimal(wallet.balance)

        is_valid = (
            available == expected_available
            and pending == expected_pending
            and total == expected_total
            and available >= Decimal("0")
            and pending >= Decimal("0")
        )

        return {
            "store_id": store_id,
            "wallet_id": wallet.id,
            "is_valid": is_valid,
            "computed": {
                "available_balance": str(available),
                "pending_balance": str(pending),
                "balance": str(total),
            },
            "stored": {
                "available_balance": str(expected_available),
                "pending_balance": str(expected_pending),
                "balance": str(expected_total),
            },
            "transaction_count": txns.count(),
        }

    @staticmethod
    def get_wallet_summary(*, store_id: int, tenant_id: int | None = None) -> dict:
        """Get complete wallet summary including pending withdrawals."""
        from django.db import models
        
        wallet = WalletService.get_or_create_wallet(store_id=store_id, tenant_id=tenant_id)
        
        pending_withdrawals = WithdrawalRequest.objects.filter(
            wallet=wallet,
            status=WithdrawalRequest.STATUS_PENDING
        ).aggregate(total=models.Sum("amount"))
        
        pending_withdrawal_amount = WalletService._to_decimal(pending_withdrawals["total"] or "0")
        effective_available = WalletService._to_decimal(
            wallet.available_balance - pending_withdrawal_amount
        )
        
        return {
            "wallet_id": wallet.id,
            "store_id": store_id,
            "currency": wallet.currency,
            "available_balance": str(wallet.available_balance),
            "pending_balance": str(wallet.pending_balance),
            "balance": str(wallet.balance),
            "pending_withdrawal_amount": str(pending_withdrawal_amount),
            "effective_available_balance": str(effective_available),
            "is_active": wallet.is_active,
        }

    @staticmethod
    def get_withdrawal_request(*, withdrawal_id: int) -> WithdrawalRequest | None:
        """Retrieve a specific withdrawal request."""
        return WithdrawalRequest.objects.filter(id=withdrawal_id).first()

    @staticmethod
    def get_withdrawal_request_by_reference(*, reference_code: str) -> WithdrawalRequest | None:
        """Retrieve a specific withdrawal request by reference code."""
        return WithdrawalRequest.objects.filter(reference_code=reference_code).first()

    @staticmethod
    def list_wallet_transactions(
        *,
        store_id: int,
        tenant_id: int | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[WalletTransaction]:
        """List wallet transactions with optional filtering."""
        wallet = WalletService.get_or_create_wallet(store_id=store_id, tenant_id=tenant_id)
        query = WalletTransaction.objects.filter(wallet=wallet).order_by("-created_at")
        
        if event_type:
            query = query.filter(event_type=event_type)
        
        return list(query[:limit])

    @staticmethod
    def list_withdrawal_requests(
        *,
        store_id: int,
        tenant_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[WithdrawalRequest]:
        """List withdrawal requests with optional filtering."""
        query = WithdrawalRequest.objects.filter(store_id=store_id)
        
        if tenant_id:
            query = query.filter(tenant_id=tenant_id)
        if status:
            query = query.filter(status=status)
        
        return list(query.order_by("-requested_at")[:limit])

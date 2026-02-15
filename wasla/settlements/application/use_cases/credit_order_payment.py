from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from orders.models import Order
from settlements.domain.errors import LedgerError
from settlements.domain.policies import ensure_non_negative_amount
from settlements.infrastructure.repositories import get_or_create_ledger_account
from settlements.models import LedgerEntry


@dataclass(frozen=True)
class CreditOrderPaymentCommand:
    order_id: int


class CreditOrderPaymentUseCase:
    """
    Credit a paid order into the pending ledger balance.
    Idempotent per order.
    """

    @staticmethod
    @transaction.atomic
    def execute(cmd: CreditOrderPaymentCommand) -> LedgerEntry:
        order = Order.objects.select_for_update().filter(id=cmd.order_id).first()
        if not order:
            raise LedgerError("Order not found.")
        if order.payment_status != "paid" and order.status != "paid":
            raise LedgerError("Order is not paid.")

        existing = LedgerEntry.objects.filter(order_id=order.id).first()
        if existing:
            return existing

        amount = ensure_non_negative_amount(Decimal(order.total_amount), field="order_total")
        account = get_or_create_ledger_account(store_id=order.store_id, currency=order.currency)
        if account.currency != order.currency:
            raise LedgerError("Currency mismatch for ledger account.")

        entry = LedgerEntry.objects.create(
            store_id=order.store_id,
            order=order,
            entry_type=LedgerEntry.TYPE_CREDIT,
            amount=amount,
            currency=order.currency,
            description="Order payment credited to pending balance",
        )

        account.pending_balance = Decimal(account.pending_balance) + amount
        account.save(update_fields=["pending_balance"])
        return entry

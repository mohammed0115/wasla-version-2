from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError, transaction

from apps.payments.models import PaymentAttempt
from apps.settlements.models import SettlementRecord


@transaction.atomic
def process_successful_payment(payment_attempt_id: int) -> SettlementRecord:
    payment_attempt = (
        PaymentAttempt.objects.select_for_update()
        .select_related("store", "order")
        .filter(id=payment_attempt_id)
        .first()
    )
    if not payment_attempt:
        raise ValueError("payment_attempt_not_found")

    if payment_attempt.status != PaymentAttempt.STATUS_PAID:
        raise ValueError("payment_attempt_not_paid")

    existing = (
        SettlementRecord.objects.select_for_update()
        .filter(payment_attempt_id=payment_attempt.id)
        .first()
    )
    if existing:
        return existing

    gross_amount = Decimal(payment_attempt.amount)
    wasla_fee = Decimal("1.00")
    net_amount = gross_amount - wasla_fee

    try:
        return SettlementRecord.objects.create(
            store=payment_attempt.store,
            order=payment_attempt.order,
            payment_attempt=payment_attempt,
            gross_amount=gross_amount,
            wasla_fee=wasla_fee,
            net_amount=net_amount,
            status=SettlementRecord.STATUS_PENDING,
        )
    except IntegrityError:
        return SettlementRecord.objects.get(payment_attempt_id=payment_attempt.id)

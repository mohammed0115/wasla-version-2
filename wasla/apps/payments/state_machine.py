from __future__ import annotations

import logging

from apps.payments.models import PaymentAttempt

logger = logging.getLogger(__name__)


ALLOWED_TRANSITIONS = {
    PaymentAttempt.STATUS_INITIATED: {
        PaymentAttempt.STATUS_PENDING,
        PaymentAttempt.STATUS_FAILED,
        PaymentAttempt.STATUS_FLAGGED,
        PaymentAttempt.STATUS_RETRY_PENDING,
    },
    PaymentAttempt.STATUS_PENDING: {
        PaymentAttempt.STATUS_CONFIRMED,
        PaymentAttempt.STATUS_FAILED,
        PaymentAttempt.STATUS_REFUNDED,
        PaymentAttempt.STATUS_FLAGGED,
        PaymentAttempt.STATUS_RETRY_PENDING,
    },
    PaymentAttempt.STATUS_RETRY_PENDING: {
        PaymentAttempt.STATUS_PENDING,
        PaymentAttempt.STATUS_FAILED,
    },
    PaymentAttempt.STATUS_FLAGGED: {
        PaymentAttempt.STATUS_PENDING,
        PaymentAttempt.STATUS_FAILED,
    },
    PaymentAttempt.STATUS_CONFIRMED: {
        PaymentAttempt.STATUS_REFUNDED,
    },
    PaymentAttempt.STATUS_FAILED: set(),
    PaymentAttempt.STATUS_REFUNDED: set(),
}


def can_transition(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in ALLOWED_TRANSITIONS.get(current, set())


def transition_payment_attempt_status(
    attempt: PaymentAttempt,
    target_status: str,
    *,
    reason: str = "",
) -> bool:
    current_status = attempt.status
    if not can_transition(current_status, target_status):
        logger.warning(
            "invalid_payment_state_transition",
            extra={
                "payment_attempt_id": attempt.id,
                "store_id": attempt.store_id,
                "order_id": attempt.order_id,
                "current_status": current_status,
                "target_status": target_status,
                "reason": reason,
            },
        )
        return False

    if current_status != target_status:
        attempt.status = target_status
        attempt.save(update_fields=["status", "updated_at"])
    return True

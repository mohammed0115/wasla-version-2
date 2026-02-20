from core.domain.exceptions import ConflictError
from apps.payments.domain.payment_status import PaymentStatus


ALLOWED_PAYMENT_TRANSITIONS = {
    PaymentStatus.CREATED: {PaymentStatus.PENDING, PaymentStatus.FAILED},
    PaymentStatus.PENDING: {PaymentStatus.PAID, PaymentStatus.FAILED},
    PaymentStatus.PAID: {PaymentStatus.REFUNDED},
    PaymentStatus.FAILED: set(),
    PaymentStatus.REFUNDED: set(),
}


def assert_payment_transition(current: PaymentStatus, new: PaymentStatus) -> None:
    if new not in ALLOWED_PAYMENT_TRANSITIONS.get(current, set()):
        raise ConflictError(f"Invalid Payment transition: {current} -> {new}")

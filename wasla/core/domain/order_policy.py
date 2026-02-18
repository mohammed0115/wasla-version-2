from .exceptions import ConflictError
from .order_status import OrderStatus


ALLOWED_TRANSITIONS = {
    OrderStatus.DRAFT: [OrderStatus.PENDING_PAYMENT],
    OrderStatus.PENDING_PAYMENT: [OrderStatus.PAID, OrderStatus.CANCELLED],
    OrderStatus.PAID: [OrderStatus.FULFILLED, OrderStatus.REFUNDED],
    OrderStatus.FULFILLED: [],
    OrderStatus.CANCELLED: [],
    OrderStatus.REFUNDED: [],
}


def validate_order_transition(current_status, new_status):
    if new_status not in ALLOWED_TRANSITIONS[current_status]:
        raise ConflictError(
            f"Invalid transition from {current_status} to {new_status}"
        )

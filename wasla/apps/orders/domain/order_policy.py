# from .exceptions import ConflictError
# from .order_status import OrderStatus


# ALLOWED_TRANSITIONS = {
#     OrderStatus.DRAFT: [OrderStatus.PENDING_PAYMENT],
#     OrderStatus.PENDING_PAYMENT: [OrderStatus.PAID, OrderStatus.CANCELLED],
#     OrderStatus.PAID: [OrderStatus.FULFILLED, OrderStatus.REFUNDED],
#     OrderStatus.FULFILLED: [],
#     OrderStatus.CANCELLED: [],
#     OrderStatus.REFUNDED: [],
# }


# def validate_order_transition(current_status, new_status):
#     if new_status not in ALLOWED_TRANSITIONS[current_status]:
#         raise ConflictError(
#             f"Invalid transition from {current_status} to {new_status}"
#         )
from core.domain.exceptions import ConflictError
from apps.orders.domain.order_status import OrderStatus


ALLOWED_ORDER_TRANSITIONS = {
    OrderStatus.DRAFT: {OrderStatus.PENDING_PAYMENT},
    OrderStatus.PENDING_PAYMENT: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.FULFILLED, OrderStatus.REFUNDED},
    OrderStatus.FULFILLED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.REFUNDED: set(),
}


def assert_order_transition(current: OrderStatus, new: OrderStatus) -> None:
    allowed = ALLOWED_ORDER_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise ConflictError(f"Invalid Order transition: {current} -> {new}")

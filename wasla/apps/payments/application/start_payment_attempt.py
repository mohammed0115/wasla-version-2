from core.application.usecase import UseCase, UseCaseResult
from apps.payments.domain.payment_status import PaymentStatus
from core.domain.exceptions import ConflictError


class StartPaymentAttempt(UseCase):

    def execute(self, order, amount, idempotency_key):
        if order.status != "pending_payment":
            return UseCaseResult(
                ok=False,
                error="Order is not ready for payment"
            )

        payment_data = {
            "order_id": order.id,
            "amount": amount,
            "status": PaymentStatus.CREATED.value,
            "idempotency_key": idempotency_key,
        }

        return UseCaseResult(ok=True, data=payment_data)

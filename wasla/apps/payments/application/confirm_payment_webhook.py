from core.application.usecase import UseCase, UseCaseResult
from apps.payments.domain.payment_status import PaymentStatus
from apps.payments.domain.payment_policy import assert_payment_transition
from core.domain.exceptions import ConflictError


class ConfirmPaymentWebhook(UseCase):
    """
    Confirms a payment ONLY from webhook (trusted path).
    Must be idempotent: if webhook repeats, result is safe.
    """

    def execute(self, payment_attempt, provider_reference: str):
        # Idempotency: already paid -> return ok without changes
        if payment_attempt.status == PaymentStatus.PAID.value:
            return UseCaseResult(ok=True, data={"already_confirmed": True})

        # Only pending payments can become paid
        current = PaymentStatus(payment_attempt.status)
        new = PaymentStatus.PAID
        assert_payment_transition(current, new)

        # Apply state change (actual DB update happens in repository/service layer)
        payment_attempt.status = new.value
        payment_attempt.provider_reference = provider_reference

        return UseCaseResult(ok=True, data={"payment_status": new.value})

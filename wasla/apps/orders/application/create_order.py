from core.application.usecase import UseCase, UseCaseResult
from apps.orders.domain.order_status import OrderStatus


class CreateOrder(UseCase):

    def execute(self, tenant, customer, items):
        if not items:
            return UseCaseResult(ok=False, error="Order must contain items")

        order_data = {
            "tenant": tenant,
            "customer": customer,
            "status": OrderStatus.DRAFT.value,
            "items": items,
        }

        return UseCaseResult(ok=True, data=order_data)

from django.db import transaction
from ..models import Payment
from .gateway_service import PaymentGatewayService
from apps.orders.services.order_service import OrderService


class PaymentService:
    @staticmethod
    @transaction.atomic
    def initiate_payment(order, method):
        if not method:
            raise ValueError("Payment method is required")
        if order.status != "pending":
            raise ValueError("Payment allowed only for pending orders")

        OrderService.validate_stock(order)

        payment = Payment.objects.create(
            tenant_id=order.tenant_id or order.store_id,
            order=order,
            method=method,
            status="pending",
            amount=order.total_amount
        )

        response = PaymentGatewayService.charge(
            amount=payment.amount,
            method=method,
            metadata={"order": order.order_number}
        )

        if response["success"]:
            OrderService.mark_as_paid(order)
            payment.status = "success"
            payment.reference = response["reference"]
            payment.save(update_fields=["status", "reference"])
        else:
            payment.status = "failed"
            payment.save(update_fields=["status"])

        return payment

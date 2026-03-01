from __future__ import annotations

import uuid
from decimal import Decimal

from apps.payments.models import Payment


class PaymentGatewayClient:
    """
    Minimal payment gateway client abstraction used by refund workflows.

    This stub can be swapped with real provider integrations later.
    """

    def __init__(self, tenant_id: int | None = None):
        self.tenant_id = tenant_id

    def request_refund(
        self,
        *,
        order_id: int,
        amount: Decimal,
        reason: str = "",
        metadata: dict | None = None,
    ) -> dict:
        payment = (
            Payment.objects.filter(order_id=order_id, status="success")
            .order_by("-created_at")
            .first()
        )
        if not payment:
            return {"status": "error", "error": "No successful payment found"}

        refund_id = f"RF-{uuid.uuid4().hex[:12].upper()}"
        return {
            "status": "success",
            "completed": True,
            "data": {
                "refund_id": refund_id,
                "payment_reference": payment.reference,
            },
        }


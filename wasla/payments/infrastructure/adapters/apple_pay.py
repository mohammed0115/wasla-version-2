from __future__ import annotations

from .base import HostedPaymentAdapter


class ApplePayGatewayAdapter(HostedPaymentAdapter):
    code = "apple_pay"
    name = "Apple Pay"
    payment_method = "apple_pay"

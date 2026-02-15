from __future__ import annotations

from .base import HostedPaymentAdapter


class MadaGatewayAdapter(HostedPaymentAdapter):
    code = "mada"
    name = "Mada"
    payment_method = "card"
    scheme = "mada"


class VisaGatewayAdapter(HostedPaymentAdapter):
    code = "visa"
    name = "Visa"
    payment_method = "card"
    scheme = "visa"


class MastercardGatewayAdapter(HostedPaymentAdapter):
    code = "mastercard"
    name = "Mastercard"
    payment_method = "card"
    scheme = "mastercard"

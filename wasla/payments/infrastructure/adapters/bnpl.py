from __future__ import annotations

from .base import HostedPaymentAdapter


class TabbyGatewayAdapter(HostedPaymentAdapter):
    code = "tabby"
    name = "Tabby (BNPL)"
    payment_method = "bnpl"
    scheme = "tabby"


class TamaraGatewayAdapter(HostedPaymentAdapter):
    code = "tamara"
    name = "Tamara (BNPL)"
    payment_method = "bnpl"
    scheme = "tamara"

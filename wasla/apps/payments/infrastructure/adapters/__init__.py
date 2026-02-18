"""Payment adapters for real providers."""

from .apple_pay import ApplePayGatewayAdapter
from .bnpl import TabbyGatewayAdapter, TamaraGatewayAdapter
from .cards import MadaGatewayAdapter, MastercardGatewayAdapter, VisaGatewayAdapter

__all__ = [
    "ApplePayGatewayAdapter",
    "TabbyGatewayAdapter",
    "TamaraGatewayAdapter",
    "MadaGatewayAdapter",
    "MastercardGatewayAdapter",
    "VisaGatewayAdapter",
]

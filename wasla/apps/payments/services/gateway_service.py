
from core.infrastructure.circuit_breaker import CircuitBreaker


class PaymentGatewayService:
    @staticmethod
    def charge(amount, method, metadata=None):
        breaker = CircuitBreaker("payments.gateway")

        def _call():
            # TODO: Replace with real provider integration.
            return {
                "success": True,
                "reference": "GATEWAY-REF-123456",
            }

        return breaker.call(_call)

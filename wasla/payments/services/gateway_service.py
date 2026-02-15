
class PaymentGatewayService:
    @staticmethod
    def charge(amount, method, metadata=None):
        return {
            "success": True,
            "reference": "GATEWAY-REF-123456"
        }

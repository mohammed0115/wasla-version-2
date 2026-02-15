
from decimal import Decimal

class PricingService:
    @staticmethod
    def calculate_total(items):
        total = Decimal("0.00")
        for item in items:
            total += item["price"] * item["quantity"]
        return total

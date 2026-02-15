
class CarrierService:
    @staticmethod
    def create_shipment(order, carrier):
        return {
            "tracking_number": f"{carrier.upper()}-TRK-123456"
        }

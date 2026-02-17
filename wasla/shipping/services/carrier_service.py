import uuid
from datetime import datetime


class CarrierService:
    """
    Shipment carrier service supporting multiple carrier types.
    Extensible via adapter pattern for real carrier integrations.
    """

    CARRIERS = {
        "manual_delivery": {"name": "Manual Delivery", "code": "MAN"},
        "pickup": {"name": "Store Pickup", "code": "PKP"},
        "courier_basic": {"name": "Courier Basic", "code": "CB"},
        "courier_express": {"name": "Courier Express", "code": "EX"},
    }

    @staticmethod
    def create_shipment(order, carrier: str) -> dict:
        """
        Create a shipment with tracking number.
        Supports multiple carrier types and can be extended for real APIs.
        """
        if not carrier:
            carrier = "manual_delivery"

        carrier_info = CarrierService.CARRIERS.get(carrier, CarrierService.CARRIERS["manual_delivery"])
        tracking_code = carrier_info["code"]
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8].upper()
        tracking_number = f"{tracking_code}-{timestamp}-{unique_id}"

        return {
            "tracking_number": tracking_number,
            "carrier_name": carrier_info["name"],
            "carrier_code": carrier,
            "created_at": timestamp,
        }

    @staticmethod
    def validate_carrier(carrier: str) -> bool:
        """Validate if carrier type is supported."""
        return carrier in CarrierService.CARRIERS

    @staticmethod
    def get_supported_carriers() -> list[str]:
        """Return list of supported carrier codes."""
        return list(CarrierService.CARRIERS.keys())

from decimal import Decimal
from apps.shipping.models import ShippingRate, ShippingZone


class ShippingCalculationService:
    """Service to calculate shipping costs based on zones and rates."""

    def find_zone_for_country(self, store, country_code):
        """Find shipping zone for a country."""
        zones = ShippingZone.objects.filter(
            store=store,
            is_active=True,
        ).order_by("-priority")

        for zone in zones:
            if zone.covers_country(country_code):
                return zone

        return None

    def calculate_shipping_cost(self, store, country_code, weight, order_total):
        """
        Calculate shipping cost for an order.

        Args:
            store: Store instance
            country_code: ISO country code
            weight: Total weight in kg
            order_total: Order subtotal (Decimal)

        Returns:
            (shipping_cost, rate, zone) or (None, None, None) if not available
        """
        zone = self.find_zone_for_country(store, country_code)
        if not zone:
            return None, None, None

        # Find applicable rate
        rates = zone.shipping_rates.filter(is_active=True).order_by("-priority")

        for rate in rates:
            if rate.applies_to_weight(weight):
                cost = rate.calculate_cost(weight, order_total)
                if cost is not None:
                    return cost, rate, zone

        return None, None, None

    def get_available_rates_for_country(self, store, country_code):
        """Get all available shipping rates for a country."""
        zone = self.find_zone_for_country(store, country_code)
        if not zone:
            return []

        return zone.shipping_rates.filter(is_active=True).order_by("priority")


class CarrierInterface:
    """Abstract interface for shipping carriers."""

    def __init__(self, api_key=None, username=None, password=None):
        self.api_key = api_key
        self.username = username
        self.password = password

    def create_shipment(self, shipment, order):
        """
        Create a shipment with the carrier.

        Args:
            shipment: Shipment instance
            order: Order instance

        Returns:
            dict: {"tracking_number": "...", "label_url": "...", "status": "..."}
        """
        raise NotImplementedError

    def get_tracking_status(self, tracking_number):
        """Get tracking status for a shipment."""
        raise NotImplementedError

    def generate_label(self, tracking_number):
        """Generate shipping label."""
        raise NotImplementedError

    def cancel_shipment(self, tracking_number):
        """Cancel a shipment."""
        raise NotImplementedError


class AramexAdapter(CarrierInterface):
    """Aramex shipping carrier adapter."""

    def __init__(self, api_key=None, account_number=None, entity_type=None):
        super().__init__(api_key=api_key)
        self.account_number = account_number
        self.entity_type = entity_type or "SMB"

    def create_shipment(self, shipment, order):
        """Create shipment with Aramex."""
        # TODO: Integrate with Aramex API
        # This is a stub implementation
        return {
            "tracking_number": f"ARAMEX-{order.id}-{shipment.id}",
            "label_url": f"https://api.aramex.com/labels/{order.id}/{shipment.id}.pdf",
            "status": "pending",
        }

    def get_tracking_status(self, tracking_number):
        """Get Aramex tracking status."""
        # TODO: Call Aramex API with tracking_number
        return {
            "tracking_number": tracking_number,
            "status": "in_transit",
            "last_update": "2026-02-28 10:30:00",
            "location": "Riyadh, SA",
        }

    def generate_label(self, tracking_number):
        """Generate Aramex shipping label."""
        # TODO: Call label generation API
        return {
            "tracking_number": tracking_number,
            "label_url": f"https://api.aramex.com/labels/{tracking_number}.pdf",
            "format": "pdf",
        }

    def cancel_shipment(self, tracking_number):
        """Cancel Aramex shipment."""
        # TODO: Call Aramex cancellation API
        return {"tracking_number": tracking_number, "status": "cancelled"}


class SMSAAdapter(CarrierInterface):
    """SMSA Express shipping carrier adapter."""

    def __init__(self, api_key=None, customer_code=None):
        super().__init__(api_key=api_key)
        self.customer_code = customer_code

    def create_shipment(self, shipment, order):
        """Create shipment with SMSA Express."""
        # TODO: Integrate with SMSA API
        # This is a stub implementation
        return {
            "tracking_number": f"SMSA-{order.id}-{shipment.id}",
            "label_url": f"https://api.smsa.com/labels/{order.id}/{shipment.id}.pdf",
            "status": "pending",
        }

    def get_tracking_status(self, tracking_number):
        """Get SMSA tracking status."""
        # TODO: Call SMSA API with tracking_number
        return {
            "tracking_number": tracking_number,
            "status": "delivered",
            "last_update": "2026-02-28 14:45:00",
            "location": "Riyadh, SA",
        }

    def generate_label(self, tracking_number):
        """Generate SMSA shipping label."""
        # TODO: Call label generation API
        return {
            "tracking_number": tracking_number,
            "label_url": f"https://api.smsa.com/labels/{tracking_number}.pdf",
            "format": "pdf",
        }

    def cancel_shipment(self, tracking_number):
        """Cancel SMSA shipment."""
        # TODO: Call SMSA cancellation API
        return {"tracking_number": tracking_number, "status": "cancelled"}


class CarrierFactory:
    """Factory for creating carrier instances."""

    CARRIERS = {
        "aramex": AramexAdapter,
        "smsa": SMSAAdapter,
    }

    @staticmethod
    def create_carrier(carrier_name, **kwargs):
        """
        Create carrier instance.

        Args:
            carrier_name: One of 'aramex', 'smsa'
            **kwargs: Carrier-specific credentials

        Returns:
            CarrierInterface instance
        """
        adapter_class = CarrierFactory.CARRIERS.get(carrier_name.lower())
        if not adapter_class:
            raise ValueError(f"Unknown carrier: {carrier_name}")

        return adapter_class(**kwargs)

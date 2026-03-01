
from __future__ import annotations

from apps.shipping.models import ShippingZone


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

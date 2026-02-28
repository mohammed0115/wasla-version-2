"""
Shipping Zone Service - Validates shipping zones and calculates rates.

Financial Integrity Level: HIGH

This service:
- Matches customer country to shipping zone
- Calculates shipping fees based on zone + order weight/value
- Blocks checkout if no matching zone
"""

import logging
from decimal import Decimal
from typing import Dict, Optional, Any

from apps.shipping.models import ShippingZone

logger = logging.getLogger("wasla.shipping")


class ShippingZoneMatchError(Exception):
    """Raised when customer country doesn't match any zone."""
    pass


class ShippingZoneService:
    """
    Service for shipping zone matching and rate calculation.
    
    Usage:
        service = ShippingZoneService()
        try:
            rate = service.calculate_shipping_cost(
                store_id=5,
                customer_country="SA",
                order_total=Decimal("1000.00"),
                total_weight=Decimal("2.5"),  # kg
            )
            # Returns: {"cost": Decimal("50.00"), "zone_id": 1, "rate_name": "Standard"}
        except ShippingZoneMatchError as e:
            # Handle no matching zone
            logger.error(f"Shipping error: {e}")
    """
    
    def find_zone_for_country(self, store_id: int, country_code: str) -> Optional[ShippingZone]:
        """
        Find shipping zone for country.
        
        Returns zone with highest priority if multiple match.
        """
        zones = ShippingZone.objects.filter(
            store_id=store_id,
            is_active=True,
        ).order_by("-priority")
        
        for zone in zones:
            if zone.covers_country(country_code):
                return zone
        
        return None
    
    def calculate_shipping_cost(
        self,
        store_id: int,
        customer_country: str,
        order_total: Decimal,
        total_weight: Decimal = Decimal("0"),
        shipping_method: str = "standard",  # "standard", "express", etc.
    ) -> Dict[str, Any]:
        """
        Calculate shipping cost for order.
        
        Args:
            store_id: Store ID
            customer_country: Country code (e.g., "SA")
            order_total: Order subtotal
            total_weight: Total weight in kg
            shipping_method: Shipping method name
        
        Returns:
            {
                "cost": Decimal("50.00"),
                "zone_id": 1,
                "zone_name": "Saudi Arabia",
                "rate_name": "Standard",
                "base_rate": 50.00,
                "weight_cost": 0.00,
            }
        
        Raises:
            ShippingZoneMatchError if no zone matches country
        """
        zone = self.find_zone_for_country(store_id, customer_country)
        
        if not zone:
            raise ShippingZoneMatchError(
                f"No shipping zone found for country '{customer_country}'. "
                f"Please contact store for available shipping options."
            )
        
        # Find shipping rate (method)
        rate = zone.shipping_rates.filter(
            is_active=True,
            name__iexact=shipping_method,
        ).first()
        
        if not rate:
            # Default to first active rate
            rate = zone.shipping_rates.filter(is_active=True).first()
        
        if not rate:
            raise ShippingZoneMatchError(
                f"No shipping rate available for zone '{zone.name}'."
            )
        
        # Calculate cost using the model's method
        cost = rate.calculate_cost(total_weight, order_total)
        
        if cost is None:
            # Weight out of range
            raise ShippingZoneMatchError(
                f"Order weight {total_weight}kg exceeds maximum for available shipping rates."
            )
        
        return {
            "cost": cost,
            "zone_id": zone.id,
            "zone_name": zone.name,
            "rate_name": rate.name,
            "base_rate": rate.base_rate,
            "weight": total_weight,
        }
    
    def validate_shipping_for_checkout(
        self,
        store_id: int,
        customer_country: str,
    ) -> Dict[str, Any]:
        """
        Validate that shipping is available for checkout.
        
        Called during checkout to block if no zone matches.
        
        Returns:
            {
                "available": bool,
                "error": str or None,
                "zone_id": int or None,
            }
        """
        zone = self.find_zone_for_country(store_id, customer_country)
        
        if not zone:
            return {
                "available": False,
                "error": f"Shipping not available to {customer_country}",
                "zone_id": None,
            }
        
        if not zone.shipping_rates.filter(is_active=True).exists():
            return {
                "available": False,
                "error": f"No shipping rates configured for {zone.name}",
                "zone_id": zone.id,
            }
        
        return {
            "available": True,
            "error": None,
            "zone_id": zone.id,
        }

from django.db import transaction
from ..models import Shipment
from .carrier_service import CarrierService


class ShippingService:

    @staticmethod
    @transaction.atomic
    def create_shipment(order, carrier):
        if not carrier:
            raise ValueError("Carrier is required")
        if order.status != "processing":
            raise ValueError("Shipment allowed only for processing orders")

        shipment = Shipment.objects.create(
            order=order,
            carrier=carrier,
            status="ready"
        )

        carrier_response = CarrierService.create_shipment(order, carrier)
        shipment.tracking_number = carrier_response["tracking_number"]
        shipment.status = "shipped"
        shipment.save(update_fields=["tracking_number", "status"])

        order.status = "shipped"
        order.save(update_fields=["status"])

        return shipment

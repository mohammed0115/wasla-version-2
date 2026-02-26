from __future__ import annotations

from apps.shipping.models import Shipment
from apps.tenants.application.interfaces.shipment_repository_port import ShipmentRepositoryPort


class DjangoShipmentRepository(ShipmentRepositoryPort):
    def count_active_shipments(self, store_id: int) -> int:
        return Shipment.objects.filter(order__store_id=store_id).exclude(status__in=["delivered", "cancelled"]).count()

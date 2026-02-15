from __future__ import annotations

from decimal import Decimal

from checkout.domain.dtos import ShippingMethodDTO
from tenants.models import StoreShippingSettings


def list_shipping_methods(*, tenant_id: int) -> list[ShippingMethodDTO]:
    settings = StoreShippingSettings.objects.filter(tenant_id=tenant_id, is_enabled=True).first()
    if not settings:
        return [ShippingMethodDTO(code="pickup", label="Pickup", fee=Decimal("0"))]

    if settings.fulfillment_mode == StoreShippingSettings.MODE_MANUAL_DELIVERY:
        fee = settings.delivery_fee_flat or Decimal("0")
        return [
            ShippingMethodDTO(code="delivery", label="Delivery", fee=Decimal(fee)),
        ]

    if settings.fulfillment_mode == StoreShippingSettings.MODE_CARRIER:
        return [ShippingMethodDTO(code="carrier", label="Carrier", fee=Decimal("0"))]

    return [ShippingMethodDTO(code="pickup", label="Pickup", fee=Decimal("0"))]

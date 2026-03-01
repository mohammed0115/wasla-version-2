from __future__ import annotations

from decimal import Decimal

from django.conf import settings

from apps.checkout.domain.dtos import ShippingMethodDTO
from apps.shipping.services import ShippingCalculationService
from apps.stores.models import Store
from apps.tenants.models import StoreShippingSettings
from apps.catalog.models import Product


def _estimate_weight_kg(cart_summary) -> Decimal:
    if not cart_summary or not cart_summary.items:
        return Decimal("0")

    default_weight = Decimal(str(getattr(settings, "SHIPPING_DEFAULT_WEIGHT_KG", "1") or "1"))
    product_ids = {item.product_id for item in cart_summary.items}
    weights = {
        p.id: (getattr(p, "weight_kg", None) or default_weight)
        for p in Product.objects.filter(id__in=product_ids)
    }
    total = Decimal("0")
    for item in cart_summary.items:
        weight = Decimal(str(weights.get(item.product_id, default_weight)))
        total += weight * item.quantity
    return total


def list_shipping_methods(*, tenant_id: int, address: dict | None = None, cart_summary=None) -> list[ShippingMethodDTO]:
    settings = StoreShippingSettings.objects.filter(tenant_id=tenant_id, is_enabled=True).first()
    if not settings:
        return [ShippingMethodDTO(code="pickup", label="Pickup", fee=Decimal("0"))]

    if settings.fulfillment_mode == StoreShippingSettings.MODE_MANUAL_DELIVERY:
        fee = Decimal(settings.delivery_fee_flat or 0)
        if cart_summary and settings.free_shipping_threshold:
            if cart_summary.subtotal >= settings.free_shipping_threshold:
                fee = Decimal("0")
        return [
            ShippingMethodDTO(code="delivery", label="Delivery", fee=Decimal(fee)),
        ]

    if settings.fulfillment_mode == StoreShippingSettings.MODE_CARRIER:
        if not address or not cart_summary:
            return []
        country_code = (address.get("country") or address.get("country_code") or "").strip()
        if not country_code:
            return []
        store = Store.objects.filter(tenant_id=tenant_id).order_by("id").first()
        if not store:
            return []

        weight = _estimate_weight_kg(cart_summary)
        service = ShippingCalculationService()
        rates = service.get_available_rates_for_country(store, country_code)
        methods = []
        for rate in rates:
            cost = rate.calculate_cost(weight, cart_summary.subtotal)
            if cost is None:
                continue
            label = rate.name
            if rate.estimated_days:
                label = f"{label} ({rate.estimated_days} days)"
            methods.append(
                ShippingMethodDTO(
                    code=f"carrier:{rate.id}",
                    label=label,
                    fee=Decimal(cost),
                )
            )
        return methods

    return [ShippingMethodDTO(code="pickup", label="Pickup", fee=Decimal("0"))]

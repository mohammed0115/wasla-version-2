from __future__ import annotations

from decimal import Decimal

from .errors import StoreValidationError

PAYMENT_MODE_MANUAL = "manual"
PAYMENT_MODE_DUMMY = "dummy"
PAYMENT_MODE_GATEWAY = "gateway"

PAYMENT_MODES: set[str] = {
    PAYMENT_MODE_MANUAL,
    PAYMENT_MODE_DUMMY,
    PAYMENT_MODE_GATEWAY,
}

PAYMENT_MODE_CHOICES = [
    (PAYMENT_MODE_MANUAL, "Manual (offline/COD)"),
    (PAYMENT_MODE_DUMMY, "Dummy (testing)"),
    (PAYMENT_MODE_GATEWAY, "Gateway (Phase 2)"),
]

FULFILLMENT_MODE_PICKUP = "pickup"
FULFILLMENT_MODE_MANUAL_DELIVERY = "manual_delivery"
FULFILLMENT_MODE_CARRIER = "carrier"

FULFILLMENT_MODES: set[str] = {
    FULFILLMENT_MODE_PICKUP,
    FULFILLMENT_MODE_MANUAL_DELIVERY,
    FULFILLMENT_MODE_CARRIER,
}

FULFILLMENT_MODE_CHOICES = [
    (FULFILLMENT_MODE_PICKUP, "Pickup"),
    (FULFILLMENT_MODE_MANUAL_DELIVERY, "Manual delivery"),
    (FULFILLMENT_MODE_CARRIER, "Carrier (Phase 2)"),
]


def validate_payment_settings(
    *,
    payment_mode: str,
    provider_name: str = "",
    merchant_key: str = "",
    webhook_secret: str = "",
    is_enabled: bool = True,
) -> dict:
    mode = (payment_mode or "").strip().lower()
    if mode not in PAYMENT_MODES:
        raise StoreValidationError("Invalid payment mode.", field="payment_mode")

    normalized_provider = (provider_name or "").strip()
    if mode == PAYMENT_MODE_GATEWAY and not normalized_provider:
        raise StoreValidationError(
            "Provider name is required when payment mode is 'gateway'.",
            field="provider_name",
        )

    return {
        "payment_mode": mode,
        "provider_name": normalized_provider,
        "merchant_key": (merchant_key or "").strip(),
        "webhook_secret": (webhook_secret or "").strip(),
        "is_enabled": bool(is_enabled),
    }


def _validate_non_negative_money(value: Decimal | None, *, field: str) -> Decimal | None:
    if value is None:
        return None
    if value < 0:
        raise StoreValidationError("Value must be greater than or equal to 0.", field=field)
    return value


def validate_shipping_settings(
    *,
    fulfillment_mode: str,
    origin_city: str = "",
    delivery_fee_flat: Decimal | None = None,
    free_shipping_threshold: Decimal | None = None,
    is_enabled: bool = True,
) -> dict:
    mode = (fulfillment_mode or "").strip().lower()
    if mode not in FULFILLMENT_MODES:
        raise StoreValidationError("Invalid fulfillment mode.", field="fulfillment_mode")

    normalized_city = (origin_city or "").strip()
    if mode != FULFILLMENT_MODE_PICKUP and not normalized_city:
        raise StoreValidationError(
            "Origin city is required unless fulfillment mode is pickup.",
            field="origin_city",
        )

    delivery_fee_flat = _validate_non_negative_money(delivery_fee_flat, field="delivery_fee_flat")
    free_shipping_threshold = _validate_non_negative_money(
        free_shipping_threshold, field="free_shipping_threshold"
    )

    return {
        "fulfillment_mode": mode,
        "origin_city": normalized_city,
        "delivery_fee_flat": delivery_fee_flat,
        "free_shipping_threshold": free_shipping_threshold,
        "is_enabled": bool(is_enabled),
    }

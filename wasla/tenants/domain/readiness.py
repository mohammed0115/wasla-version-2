from __future__ import annotations

from dataclasses import dataclass

from tenants.domain.setup_policies import (
    FULFILLMENT_MODE_PICKUP,
    FULFILLMENT_MODES,
    PAYMENT_MODE_GATEWAY,
    PAYMENT_MODES,
)


@dataclass(frozen=True)
class ReadinessItem:
    key: str
    label: str
    ok: bool
    message: str = ""


@dataclass(frozen=True)
class StoreReadinessSnapshot:
    tenant_is_active: bool
    store_info_completed: bool
    setup_step: int
    is_setup_complete: bool
    payment_mode: str | None
    payment_provider_name: str | None
    shipping_mode: str | None
    shipping_origin_city: str | None
    active_products_count: int


@dataclass(frozen=True)
class StoreReadinessResult:
    ok: bool
    items: tuple[ReadinessItem, ...]
    errors: tuple[str, ...]


class StoreReadinessChecker:
    @staticmethod
    def check(snapshot: StoreReadinessSnapshot) -> StoreReadinessResult:
        errors: list[str] = []
        items: list[ReadinessItem] = []

        tenant_active_ok = bool(snapshot.tenant_is_active)
        if not tenant_active_ok:
            errors.append("Store is inactive.")
        items.append(
            ReadinessItem(
                key="tenant_active",
                label="Tenant is active",
                ok=tenant_active_ok,
                message="" if tenant_active_ok else "Activate the tenant or contact support.",
            )
        )

        store_info_ok = bool(snapshot.store_info_completed)
        if not store_info_ok:
            errors.append("Store info is not completed.")
        items.append(
            ReadinessItem(
                key="store_info",
                label="Store info completed",
                ok=store_info_ok,
                message="" if store_info_ok else "Complete store information setup first.",
            )
        )

        setup_step_ok = bool(snapshot.is_setup_complete or int(snapshot.setup_step or 0) >= 4)
        if not setup_step_ok:
            errors.append("Setup wizard has not reached the activation step yet.")
        items.append(
            ReadinessItem(
                key="setup_step",
                label="Wizard progressed to activation",
                ok=setup_step_ok,
                message="" if setup_step_ok else "Complete payment and shipping steps first.",
            )
        )

        payment_mode = (snapshot.payment_mode or "").strip().lower() or None
        payment_ok = bool(payment_mode and payment_mode in PAYMENT_MODES)
        if not payment_ok:
            errors.append("Payment settings are not configured.")
        else:
            provider = (snapshot.payment_provider_name or "").strip()
            if payment_mode == PAYMENT_MODE_GATEWAY and not provider:
                payment_ok = False
                errors.append("Payment provider name is required for gateway mode.")
        items.append(
            ReadinessItem(
                key="payment",
                label="Payment configured",
                ok=payment_ok,
                message="" if payment_ok else "Save payment settings (manual/dummy for MVP).",
            )
        )

        shipping_mode = (snapshot.shipping_mode or "").strip().lower() or None
        shipping_ok = bool(shipping_mode and shipping_mode in FULFILLMENT_MODES)
        if not shipping_ok:
            errors.append("Shipping settings are not configured.")
        else:
            origin_city = (snapshot.shipping_origin_city or "").strip()
            if shipping_mode != FULFILLMENT_MODE_PICKUP and not origin_city:
                shipping_ok = False
                errors.append("Origin city is required for the selected shipping mode.")
        items.append(
            ReadinessItem(
                key="shipping",
                label="Shipping configured",
                ok=shipping_ok,
                message="" if shipping_ok else "Save shipping settings.",
            )
        )

        products_ok = int(snapshot.active_products_count or 0) >= 1
        if not products_ok:
            errors.append("Add at least one active product before activation.")
        items.append(
            ReadinessItem(
                key="products",
                label="At least one active product",
                ok=products_ok,
                message="" if products_ok else "Create a product with stock > 0 (active).",
            )
        )

        ok = not errors
        return StoreReadinessResult(ok=ok, items=tuple(items), errors=tuple(errors))


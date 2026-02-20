from __future__ import annotations

from decimal import Decimal

from apps.settlements.models import LedgerAccount, Settlement
from apps.stores.models import Store


def get_tenant_currency(store_id: int) -> str:
    store = Store.objects.select_related("tenant").filter(id=store_id).first()
    tenant = getattr(store, "tenant", None)
    return getattr(tenant, "currency", "SAR") if tenant else "SAR"


def get_or_create_ledger_account(*, store_id: int, currency: str | None = None) -> LedgerAccount:
    resolved_currency = currency or get_tenant_currency(store_id)
    tenant_id = (
        Store.objects.filter(id=store_id)
        .values_list("tenant_id", flat=True)
        .first()
    )
    account, _ = LedgerAccount.objects.get_or_create(
        tenant_id=tenant_id,
        store_id=store_id,
        currency=resolved_currency,
        defaults={"available_balance": Decimal("0"), "pending_balance": Decimal("0")},
    )
    return account


def get_ledger_account(*, store_id: int, currency: str | None = None) -> LedgerAccount | None:
    resolved_currency = currency or get_tenant_currency(store_id)
    return LedgerAccount.objects.for_tenant(store_id).filter(currency=resolved_currency).first()


def list_settlements_for_store(store_id: int):
    return Settlement.objects.for_tenant(store_id).order_by("-created_at")

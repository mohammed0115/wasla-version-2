from __future__ import annotations

from decimal import Decimal

from settlements.models import LedgerAccount, Settlement
from tenants.models import Tenant


def get_tenant_currency(store_id: int) -> str:
    tenant = Tenant.objects.filter(id=store_id).first()
    return getattr(tenant, "currency", "SAR") if tenant else "SAR"


def get_or_create_ledger_account(*, store_id: int, currency: str | None = None) -> LedgerAccount:
    resolved_currency = currency or get_tenant_currency(store_id)
    account, _ = LedgerAccount.objects.get_or_create(
        store_id=store_id,
        currency=resolved_currency,
        defaults={"available_balance": Decimal("0"), "pending_balance": Decimal("0")},
    )
    return account


def get_ledger_account(*, store_id: int, currency: str | None = None) -> LedgerAccount | None:
    resolved_currency = currency or get_tenant_currency(store_id)
    return LedgerAccount.objects.filter(store_id=store_id, currency=resolved_currency).first()


def list_settlements_for_store(store_id: int):
    return Settlement.objects.filter(store_id=store_id).order_by("-created_at")

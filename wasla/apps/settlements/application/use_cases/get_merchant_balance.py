from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apps.settlements.domain.dtos import BalanceSummary
from apps.settlements.infrastructure.repositories import get_ledger_account
from apps.tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class GetMerchantBalanceCommand:
    tenant_ctx: TenantContext


class GetMerchantBalanceUseCase:
    @staticmethod
    def execute(cmd: GetMerchantBalanceCommand) -> BalanceSummary:
        account = get_ledger_account(
            store_id=cmd.tenant_ctx.tenant_id, currency=cmd.tenant_ctx.currency
        )
        if not account:
            return BalanceSummary(
                currency=cmd.tenant_ctx.currency,
                available_balance=Decimal("0"),
                pending_balance=Decimal("0"),
            )
        return BalanceSummary(
            currency=account.currency,
            available_balance=Decimal(account.available_balance),
            pending_balance=Decimal(account.pending_balance),
        )

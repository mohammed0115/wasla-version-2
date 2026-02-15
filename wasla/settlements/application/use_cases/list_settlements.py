from __future__ import annotations

from dataclasses import dataclass

from settlements.infrastructure.repositories import list_settlements_for_store
from tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class ListSettlementsCommand:
    tenant_ctx: TenantContext


class ListSettlementsUseCase:
    @staticmethod
    def execute(cmd: ListSettlementsCommand):
        return list_settlements_for_store(cmd.tenant_ctx.tenant_id)

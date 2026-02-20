from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantContext:
    tenant_id: int
    currency: str
    user_id: int | None = None
    session_key: str | None = None
    store_id: int | None = None

    @property
    def resolved_store_id(self) -> int:
        return self.store_id or self.tenant_id

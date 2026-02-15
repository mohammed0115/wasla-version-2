from __future__ import annotations

from typing import Protocol


class VisitorRepositoryPort(Protocol):
    def count_visitors_last_7_days(self, tenant_id: int) -> int:
        ...
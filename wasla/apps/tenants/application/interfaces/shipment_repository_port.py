from __future__ import annotations

from typing import Protocol


class ShipmentRepositoryPort(Protocol):
    def count_active_shipments(self, store_id: int) -> int:
        ...

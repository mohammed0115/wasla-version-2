from __future__ import annotations

from analytics.domain.types import EventDTO


class WarehouseStub:
    @staticmethod
    def send_event(*, tenant_id: int, event: EventDTO) -> None:
        # Phase 6: no external dependencies.
        return None

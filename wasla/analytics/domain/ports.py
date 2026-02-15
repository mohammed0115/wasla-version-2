from __future__ import annotations

from typing import Protocol

from analytics.domain.types import EventDTO


class EventSinkPort(Protocol):
    def store_event(self, *, tenant_id: int, event: EventDTO) -> int:
        ...


class WarehouseSinkPort(Protocol):
    def send_event(self, *, tenant_id: int, event: EventDTO) -> None:
        ...

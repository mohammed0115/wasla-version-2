from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

from apps.analytics.domain.types import EventDTO
from apps.analytics.domain.policies import (
    hash_identifier,
    normalize_actor_type,
    redact_properties,
    validate_event_name,
)
from apps.analytics.infrastructure.db_sink import DbEventSink
from apps.analytics.infrastructure.warehouse_stub import WarehouseStub
from apps.tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class TrackEventCommand:
    tenant_id: int
    event: EventDTO


class TrackEventUseCase:
    @staticmethod
    def execute(cmd: TrackEventCommand) -> int:
        event_id = DbEventSink.store_event(tenant_id=cmd.tenant_id, event=cmd.event)
        if getattr(settings, "ANALYTICS_WAREHOUSE_ENABLED", False):
            WarehouseStub.send_event(tenant_id=cmd.tenant_id, event=_sanitize_event(cmd.event))
        return event_id


def safe_track_event(*, tenant_id: int, event: EventDTO) -> None:
    try:
        TrackEventUseCase.execute(TrackEventCommand(tenant_id=tenant_id, event=event))
    except Exception:
        return None


def _sanitize_event(event: EventDTO) -> EventDTO:
    return EventDTO(
        event_name=validate_event_name(event.event_name),
        actor_type=normalize_actor_type(event.actor_type),
        actor_id=hash_identifier(event.actor_id),
        session_key=hash_identifier(event.session_key),
        object_type=(event.object_type or "").upper() or None,
        object_id=str(event.object_id) if event.object_id is not None else None,
        properties=redact_properties(event.properties),
        user_agent=(event.user_agent or "")[:255],
        ip_address=hash_identifier(event.ip_address),
        occurred_at=event.occurred_at or timezone.now(),
    )


def track_from_tenant_ctx(
    *,
    tenant_ctx: TenantContext,
    event_name: str,
    actor_type: str,
    object_type: str | None = None,
    object_id: str | int | None = None,
    properties: dict | None = None,
) -> None:
    event = EventDTO(
        event_name=event_name,
        actor_type=actor_type,
        actor_id=tenant_ctx.user_id,
        session_key=tenant_ctx.session_key,
        object_type=object_type,
        object_id=object_id,
        properties=properties or {},
    )
    safe_track_event(tenant_id=tenant_ctx.tenant_id, event=event)


def track_platform_event(
    *,
    event_name: str,
    actor_type: str,
    actor_id: str | int | None,
    properties: dict | None = None,
) -> None:
    tenant_id = int(getattr(settings, "ANALYTICS_PLATFORM_TENANT_ID", 0) or 0)
    event = EventDTO(
        event_name=event_name,
        actor_type=actor_type,
        actor_id=actor_id,
        session_key=None,
        properties=properties or {},
    )
    safe_track_event(tenant_id=tenant_id, event=event)

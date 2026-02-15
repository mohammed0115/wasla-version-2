from __future__ import annotations

from django.utils import timezone

from analytics.domain.types import EventDTO
from analytics.models import Event
from analytics.domain.policies import (
    hash_identifier,
    normalize_actor_type,
    redact_properties,
    validate_event_name,
)


class DbEventSink:
    @staticmethod
    def store_event(*, tenant_id: int, event: EventDTO) -> int:
        event_name = validate_event_name(event.event_name)
        actor_type = normalize_actor_type(event.actor_type)
        properties = redact_properties(event.properties)

        created = Event.objects.create(
            tenant_id=tenant_id,
            event_name=event_name,
            actor_type=actor_type,
            actor_id_hash=hash_identifier(event.actor_id),
            session_key_hash=hash_identifier(event.session_key),
            object_type=(event.object_type or "").upper(),
            object_id=str(event.object_id) if event.object_id is not None else "",
            properties_json=properties,
            user_agent=(event.user_agent or "")[:255],
            ip_hash=hash_identifier(event.ip_address),
            occurred_at=event.occurred_at or timezone.now(),
        )
        return created.id

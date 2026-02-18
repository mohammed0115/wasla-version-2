from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from apps.analytics.application.track_event import TrackEventCommand, TrackEventUseCase
from apps.analytics.domain.policies import redact_properties
from apps.analytics.domain.types import ActorContext, EventDTO, ObjectRef
from apps.observability.logging import request_id_var
from apps.tenants.domain.tenant_context import TenantContext

logger = logging.getLogger("analytics.telemetry")


def actor_from_tenant_ctx(*, tenant_ctx: TenantContext, actor_type: str) -> ActorContext:
    return ActorContext(
        actor_type=actor_type,
        actor_id=tenant_ctx.user_id,
        session_key=tenant_ctx.session_key,
    )


def actor_from_user(*, user: object, actor_type: str) -> ActorContext:
    return ActorContext(
        actor_type=actor_type,
        actor_id=getattr(user, "id", None),
    )


def actor_from_request(*, request: object, actor_type: str) -> ActorContext:
    user = getattr(request, "user", None)
    session = getattr(request, "session", None)
    user_id = user.id if getattr(user, "is_authenticated", False) else None
    session_key = getattr(session, "session_key", None) if session is not None else None
    meta = getattr(request, "META", {}) or {}
    return ActorContext(
        actor_type=actor_type,
        actor_id=user_id,
        session_key=session_key,
        user_agent=meta.get("HTTP_USER_AGENT", ""),
        ip_address=meta.get("REMOTE_ADDR", ""),
        request_id=getattr(request, "request_id", None),
    )


def _resolve_request_id(actor_ctx: ActorContext) -> str | None:
    if actor_ctx.request_id:
        return actor_ctx.request_id
    return request_id_var.get()


class TelemetryService:
    @staticmethod
    def track(
        *,
        event_name: str,
        tenant_ctx: TenantContext | None,
        actor_ctx: ActorContext,
        object_ref: ObjectRef | None = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        try:
            tenant_id = (
                tenant_ctx.tenant_id
                if tenant_ctx is not None
                else int(getattr(settings, "ANALYTICS_PLATFORM_TENANT_ID", 0) or 0)
            )
            payload = dict(properties or {})
            request_id = _resolve_request_id(actor_ctx)
            if request_id and "request_id" not in payload:
                payload["request_id"] = request_id

            event = EventDTO(
                event_name=event_name,
                actor_type=actor_ctx.actor_type,
                actor_id=actor_ctx.actor_id,
                session_key=actor_ctx.session_key,
                object_type=object_ref.object_type if object_ref else None,
                object_id=object_ref.object_id if object_ref else None,
                properties=redact_properties(payload),
                user_agent=actor_ctx.user_agent,
                ip_address=actor_ctx.ip_address,
            )
            TrackEventUseCase.execute(TrackEventCommand(tenant_id=tenant_id, event=event))
        except Exception as exc:  # pragma: no cover - fail open
            logger.info("telemetry_failed", extra={"event": event_name, "error_code": exc.__class__.__name__})
            return None

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ActorContext:
    actor_type: str
    actor_id: str | int | None = None
    session_key: str | None = None
    user_agent: str | None = None
    ip_address: str | None = None
    request_id: str | None = None


@dataclass(frozen=True)
class ObjectRef:
    object_type: str | None = None
    object_id: str | int | None = None


@dataclass(frozen=True)
class EventDTO:
    event_name: str
    actor_type: str
    actor_id: str | int | None
    session_key: str | None
    object_type: str | None = None
    object_id: str | int | None = None
    properties: dict[str, Any] | None = None
    user_agent: str | None = None
    ip_address: str | None = None
    occurred_at: datetime | None = None


@dataclass(frozen=True)
class ExperimentDTO:
    key: str
    status: str
    variants: dict[str, int]


@dataclass(frozen=True)
class AssignmentDTO:
    experiment_key: str
    variant: str
    assigned: bool


@dataclass(frozen=True)
class RiskScoreDTO:
    order_id: int
    score: int
    level: str
    reasons: list[str]

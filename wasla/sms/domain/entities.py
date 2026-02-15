from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


@dataclass(frozen=True)
class SmsMessage:
    body: str
    recipients: tuple[str, ...]
    sender: str
    scheduled_at: datetime | None = None
    tenant_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


SmsDeliveryStatus = Literal["queued", "sent", "scheduled", "failed"]


@dataclass(frozen=True)
class SmsDeliveryResult:
    provider: str
    status: SmsDeliveryStatus
    provider_message_id: str | None = None
    raw: dict[str, Any] | None = None


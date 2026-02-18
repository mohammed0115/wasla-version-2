from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class EmailMessage:
    to_email: str
    subject: str
    html: str = ""
    text: str = ""
    headers: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EmailSendResult:
    provider_message_id: str = ""


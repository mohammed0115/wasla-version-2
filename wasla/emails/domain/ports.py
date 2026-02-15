from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping

from .types import EmailMessage, EmailSendResult


class EmailGatewayPort(ABC):
    @abstractmethod
    def send(self, *, message: EmailMessage) -> EmailSendResult: ...


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str = ""
    text: str = ""
    headers: Mapping[str, str] | None = None


class TemplateRendererPort(ABC):
    @abstractmethod
    def render(self, *, template_key: str, context: Mapping[str, object]) -> RenderedEmail: ...


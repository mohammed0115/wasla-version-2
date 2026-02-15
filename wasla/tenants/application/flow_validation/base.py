from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class FlowIssue:
    code: str
    message: str
    context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FlowResult:
    scenario: str
    tenant_id: int
    tenant_slug: str
    issues: tuple[FlowIssue, ...] = ()

    @property
    def ok(self) -> bool:
        return len(self.issues) == 0


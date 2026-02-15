from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class FlowStepResult:
    name: str
    ok: bool
    details: str = ""


@dataclass(frozen=True)
class FlowReport:
    name: str
    tenant_slug: str
    passed: bool
    steps: tuple[FlowStepResult, ...] = field(default_factory=tuple)

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(step.details for step in self.steps if not step.ok and step.details)

    @classmethod
    def from_steps(cls, *, name: str, tenant_slug: str, steps: Iterable[FlowStepResult]) -> "FlowReport":
        step_list = tuple(steps)
        passed = all(step.ok for step in step_list)
        return cls(name=name, tenant_slug=tenant_slug, passed=passed, steps=step_list)


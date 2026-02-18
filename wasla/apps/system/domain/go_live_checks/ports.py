from __future__ import annotations

from typing import Protocol

from apps.system.domain.go_live_checks.types import GoLiveCheckItem


class GoLiveCheckerPort(Protocol):
    category_key: str
    category_label: str

    def run(self) -> list[GoLiveCheckItem]:
        ...

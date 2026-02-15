from __future__ import annotations

from dataclasses import dataclass

LEVEL_P0 = "P0"
LEVEL_P1 = "P1"


@dataclass(frozen=True)
class GoLiveCheckItem:
    key: str
    label: str
    ok: bool
    level: str = LEVEL_P1
    message: str = ""
    category: str = ""


@dataclass(frozen=True)
class GoLiveCategoryResult:
    key: str
    label: str
    items: tuple[GoLiveCheckItem, ...]


@dataclass(frozen=True)
class GoLiveReport:
    ok: bool
    score: int
    hard_blockers: tuple[GoLiveCheckItem, ...]
    warnings: tuple[GoLiveCheckItem, ...]
    categories: tuple[GoLiveCategoryResult, ...]

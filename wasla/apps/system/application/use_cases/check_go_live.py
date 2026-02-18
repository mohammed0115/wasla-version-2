from __future__ import annotations

from dataclasses import dataclass

from apps.system.domain.go_live_checks.types import (
    GoLiveCategoryResult,
    GoLiveCheckItem,
    GoLiveReport,
    LEVEL_P0,
)
from apps.system.infrastructure.system_checkers import default_checkers


@dataclass(frozen=True)
class CheckGoLiveResult:
    report: GoLiveReport


class GoLiveChecksFacade:
    def __init__(self, checkers=None) -> None:
        self._checkers = list(checkers or default_checkers())

    def run(self) -> tuple[GoLiveCategoryResult, ...]:
        categories: list[GoLiveCategoryResult] = []
        for checker in self._checkers:
            try:
                items = checker.run()
            except Exception as exc:  # pragma: no cover - defensive
                items = [
                    GoLiveCheckItem(
                        key=f"{checker.category_key}.checker_failed",
                        label=f"{checker.category_label} checker failed",
                        ok=False,
                        level=LEVEL_P0,
                        message="Checker failed to execute. Review logs for details.",
                        category=checker.category_key,
                    )
                ]
            categories.append(
                GoLiveCategoryResult(
                    key=checker.category_key,
                    label=checker.category_label,
                    items=tuple(items),
                )
            )
        return tuple(categories)


class CheckGoLiveUseCase:
    @staticmethod
    def execute() -> GoLiveReport:
        categories = GoLiveChecksFacade().run()
        all_items = [item for category in categories for item in category.items]
        total = len(all_items)
        ok_count = sum(1 for item in all_items if item.ok)
        score = int(round((ok_count / total) * 100)) if total else 0

        hard_blockers = tuple(item for item in all_items if not item.ok and item.level == LEVEL_P0)
        warnings = tuple(item for item in all_items if not item.ok and item.level != LEVEL_P0)
        ok = len(hard_blockers) == 0

        return GoLiveReport(
            ok=ok,
            score=score,
            hard_blockers=hard_blockers,
            warnings=warnings,
            categories=categories,
        )

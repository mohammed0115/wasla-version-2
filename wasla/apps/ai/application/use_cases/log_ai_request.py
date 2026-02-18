from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apps.ai.models import AIRequestLog


@dataclass(frozen=True)
class LogAIRequestCommand:
    store_id: int
    feature: str
    provider: str
    latency_ms: int
    token_count: int | None
    cost_estimate: Decimal
    status: str


class LogAIRequestUseCase:
    @staticmethod
    def execute(cmd: LogAIRequestCommand) -> AIRequestLog:
        return AIRequestLog.objects.create(
            store_id=cmd.store_id,
            feature=cmd.feature,
            provider=cmd.provider,
            latency_ms=cmd.latency_ms,
            token_count=cmd.token_count,
            cost_estimate=cmd.cost_estimate,
            status=cmd.status,
        )

from dataclasses import dataclass
from typing import Any, Optional, Dict


@dataclass(frozen=True)
class UseCaseResult:
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class UseCase:
    def execute(self, *args, **kwargs) -> UseCaseResult:
        raise NotImplementedError("UseCase.execute() must be implemented")

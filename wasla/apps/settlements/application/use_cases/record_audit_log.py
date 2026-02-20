from __future__ import annotations

from dataclasses import dataclass

from apps.settlements.models import AuditLog


@dataclass(frozen=True)
class RecordAuditLogCommand:
    actor_id: int | None
    store_id: int | None
    action: str
    payload: dict


class RecordAuditLogUseCase:
    @staticmethod
    def execute(cmd: RecordAuditLogCommand) -> AuditLog:
        return AuditLog.objects.create(
            actor_id=cmd.actor_id,
            tenant_id=cmd.store_id,
            store_id=cmd.store_id,
            action=cmd.action,
            payload_json=cmd.payload or {},
        )

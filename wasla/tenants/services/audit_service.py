from __future__ import annotations

from tenants.models import Tenant, TenantAuditLog


class TenantAuditService:
    @staticmethod
    def record_action(
        tenant: Tenant,
        action: str,
        *,
        actor: str = "system",
        details: str = "",
        metadata: dict | None = None,
    ) -> TenantAuditLog:
        return TenantAuditLog.objects.create(
            tenant=tenant,
            action=action,
            actor=actor,
            details=details,
            metadata=metadata or {},
        )

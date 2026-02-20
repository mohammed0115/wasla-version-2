from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Count

from apps.analytics.models import Event
from apps.tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class ReportKpisCommand:
    tenant_ctx: TenantContext


class ReportKpisUseCase:
    @staticmethod
    def execute(cmd: ReportKpisCommand) -> dict:
        qs = Event.objects.filter(tenant_id=cmd.tenant_ctx.store_id)
        by_name = list(qs.values("event_name").annotate(total=Count("id")).order_by("-total")[:20])
        return {"events_total": qs.count(), "events_by_name": by_name}

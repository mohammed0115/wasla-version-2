from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

from apps.exports.infrastructure.exporters import OrdersCSVExporter
from apps.orders.models import Order
from apps.tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class ExportOrdersCSVCommand:
    tenant_ctx: TenantContext
    actor_id: int | None
    status: str = ""
    date_from: str = ""
    date_to: str = ""


class ExportOrdersCSVUseCase:
    @staticmethod
    def execute(cmd: ExportOrdersCSVCommand):
        qs = Order.objects.for_tenant(cmd.tenant_ctx.store_id).order_by("-created_at")
        if cmd.status:
            qs = qs.filter(status=cmd.status)
        if cmd.date_from:
            start = _parse_date(cmd.date_from)
            if start:
                qs = qs.filter(created_at__date__gte=start)
        if cmd.date_to:
            end = _parse_date(cmd.date_to)
            if end:
                qs = qs.filter(created_at__date__lte=end)
        return OrdersCSVExporter.stream(qs)


def _parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None

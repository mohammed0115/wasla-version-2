from __future__ import annotations

from dataclasses import dataclass

from exports.domain.errors import ExportNotFoundError
from exports.infrastructure.exporters import InvoicePDFExporter
from orders.models import Order
from tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class ExportInvoicePDFCommand:
    tenant_ctx: TenantContext
    actor_id: int | None
    order_id: int


class ExportInvoicePDFUseCase:
    @staticmethod
    def execute(cmd: ExportInvoicePDFCommand) -> bytes:
        order = Order.objects.filter(id=cmd.order_id, store_id=cmd.tenant_ctx.tenant_id).first()
        if not order:
            raise ExportNotFoundError("Order not found.")
        return InvoicePDFExporter.render(order)

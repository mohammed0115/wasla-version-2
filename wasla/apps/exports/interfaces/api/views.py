from __future__ import annotations

from django.http import HttpResponse, StreamingHttpResponse
from rest_framework.views import APIView

from apps.exports.application.use_cases.export_invoice_pdf import (
    ExportInvoicePDFCommand,
    ExportInvoicePDFUseCase,
)
from apps.exports.application.use_cases.export_orders_csv import (
    ExportOrdersCSVCommand,
    ExportOrdersCSVUseCase,
)
from apps.exports.domain.errors import ExportNotFoundError
from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.guards import require_store, require_tenant


def _build_tenant_context(request) -> TenantContext:
    store = require_store(request)
    tenant = require_tenant(request)
    tenant_id = tenant.id
    store_id = store.id
    currency = getattr(tenant, "currency", "SAR")
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    user_id = request.user.id if request.user.is_authenticated else None
    return TenantContext(
        tenant_id=tenant_id,
        store_id=store_id,
        currency=currency,
        user_id=user_id,
        session_key=session_key,
    )


class ExportOrdersCSVAPI(APIView):
    def get(self, request):
        tenant_ctx = _build_tenant_context(request)
        stream = ExportOrdersCSVUseCase.execute(
            ExportOrdersCSVCommand(
                tenant_ctx=tenant_ctx,
                actor_id=request.user.id if request.user.is_authenticated else None,
                status=request.GET.get("status", ""),
                date_from=request.GET.get("date_from", ""),
                date_to=request.GET.get("date_to", ""),
            )
        )
        response = StreamingHttpResponse(stream, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="orders.csv"'
        return response


class ExportInvoicePDFAPI(APIView):
    def get(self, request, order_id: int):
        tenant_ctx = _build_tenant_context(request)
        try:
            content = ExportInvoicePDFUseCase.execute(
                ExportInvoicePDFCommand(
                    tenant_ctx=tenant_ctx,
                    actor_id=request.user.id if request.user.is_authenticated else None,
                    order_id=order_id,
                )
            )
        except ExportNotFoundError:
            return HttpResponse("Not found", status=404)
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="invoice-{order_id}.pdf"'
        return response

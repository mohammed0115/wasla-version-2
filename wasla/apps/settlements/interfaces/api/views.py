from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from apps.cart.interfaces.api.responses import api_response
from apps.settlements.application.use_cases.approve_settlement import (
    ApproveSettlementCommand,
    ApproveSettlementUseCase,
)
from apps.settlements.application.use_cases.generate_monthly_invoice_draft import (
    generate_monthly_invoice_draft,
)
from apps.settlements.application.use_cases.generate_monthly_report import (
    generate_monthly_report,
)
from apps.settlements.application.use_cases.get_merchant_balance import (
    GetMerchantBalanceCommand,
    GetMerchantBalanceUseCase,
)
from apps.settlements.application.use_cases.get_settlement_detail import (
    GetSettlementDetailCommand,
    GetSettlementDetailUseCase,
)
from apps.settlements.application.use_cases.list_settlements import (
    ListSettlementsCommand,
    ListSettlementsUseCase,
)
from apps.settlements.application.use_cases.mark_settlement_paid import (
    MarkSettlementPaidCommand,
    MarkSettlementPaidUseCase,
)
from apps.settlements.domain.errors import InvalidSettlementStateError, SettlementNotFoundError
from apps.settlements.interfaces.api.serializers import (
    BalanceSerializer,
    SettlementDetailSerializer,
    SettlementSerializer,
)
from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.guards import require_merchant, require_store, require_tenant


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


class MerchantBalanceAPI(APIView):
    def get(self, request):
        tenant_ctx = _build_tenant_context(request)
        balance = GetMerchantBalanceUseCase.execute(GetMerchantBalanceCommand(tenant_ctx=tenant_ctx))
        return api_response(success=True, data=BalanceSerializer(balance).data)


class MerchantSettlementsAPI(APIView):
    def get(self, request):
        tenant_ctx = _build_tenant_context(request)
        settlements = ListSettlementsUseCase.execute(ListSettlementsCommand(tenant_ctx=tenant_ctx))
        serializer = SettlementSerializer(settlements, many=True)
        return api_response(success=True, data={"items": serializer.data})


class MerchantSettlementDetailAPI(APIView):
    def get(self, request, settlement_id: int):
        tenant_ctx = _build_tenant_context(request)
        try:
            detail = GetSettlementDetailUseCase.execute(
                GetSettlementDetailCommand(settlement_id=settlement_id, store_id=tenant_ctx.store_id)
            )
        except SettlementNotFoundError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_404_NOT_FOUND)
        serializer = SettlementDetailSerializer(detail)
        return api_response(success=True, data=serializer.data)


class AdminApproveSettlementAPI(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, settlement_id: int):
        try:
            settlement = ApproveSettlementUseCase.execute(
                ApproveSettlementCommand(settlement_id=settlement_id, actor_id=request.user.id)
            )
        except SettlementNotFoundError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_404_NOT_FOUND)
        except InvalidSettlementStateError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_409_CONFLICT)
        return api_response(success=True, data=SettlementSerializer(settlement).data)


class AdminMarkSettlementPaidAPI(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, settlement_id: int):
        try:
            settlement = MarkSettlementPaidUseCase.execute(
                MarkSettlementPaidCommand(settlement_id=settlement_id, actor_id=request.user.id)
            )
        except SettlementNotFoundError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_404_NOT_FOUND)
        except InvalidSettlementStateError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_409_CONFLICT)
        return api_response(success=True, data=SettlementSerializer(settlement).data)


class MerchantMonthlyReportAPI(APIView):
    def get(self, request):
        store = require_store(request)
        require_merchant(request)
        tenant = getattr(store, "tenant", None)
        if not tenant:
            return api_response(success=False, errors=["tenant_not_found"], status_code=status.HTTP_404_NOT_FOUND)

        try:
            year = int(request.query_params.get("year"))
            month = int(request.query_params.get("month"))
        except (TypeError, ValueError):
            return api_response(success=False, errors=["invalid_year_or_month"], status_code=status.HTTP_400_BAD_REQUEST)

        try:
            report = generate_monthly_report(tenant_id=tenant.id, year=year, month=month)
        except ValueError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_400_BAD_REQUEST)

        return api_response(
            success=True,
            data={
                "tenant_id": report.tenant_id,
                "year": report.year,
                "month": report.month,
                "total_operations": report.total_operations,
                "total_wasla_fee": str(report.total_wasla_fee),
                "settlement_ids": report.settlement_ids,
            },
        )


class MerchantInvoiceDraftAPI(APIView):
    def post(self, request):
        store = require_store(request)
        require_merchant(request)
        tenant = getattr(store, "tenant", None)
        if not tenant:
            return api_response(success=False, errors=["tenant_not_found"], status_code=status.HTTP_404_NOT_FOUND)

        try:
            year = int(request.data.get("year"))
            month = int(request.data.get("month"))
        except (TypeError, ValueError):
            return api_response(success=False, errors=["invalid_year_or_month"], status_code=status.HTTP_400_BAD_REQUEST)

        try:
            result = generate_monthly_invoice_draft(tenant_id=tenant.id, year=year, month=month)
        except ValueError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_400_BAD_REQUEST)

        invoice = result.invoice
        return api_response(
            success=True,
            data={
                "invoice_id": invoice.id,
                "tenant_id": invoice.tenant_id,
                "year": invoice.year,
                "month": invoice.month,
                "status": invoice.status,
                "total_operations": invoice.total_operations,
                "total_wasla_fee": str(invoice.total_wasla_fee),
                "created": result.created,
            },
            status_code=status.HTTP_201_CREATED if result.created else status.HTTP_200_OK,
        )

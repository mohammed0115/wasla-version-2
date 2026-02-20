from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.settlements.application.use_cases.approve_settlement import (
    ApproveSettlementCommand,
    ApproveSettlementUseCase,
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
from apps.settlements.models import Settlement, SettlementItem
from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.guards import require_store, require_tenant
from apps.tenants.interfaces.web.decorators import tenant_access_required


def _build_tenant_context(request: HttpRequest) -> TenantContext:
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


@login_required
@tenant_access_required
def balance_view(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    balance = GetMerchantBalanceUseCase.execute(GetMerchantBalanceCommand(tenant_ctx=tenant_ctx))
    context = {"balance": balance, "tenant": request.tenant}
    return render(request, "dashboard/balance.html", context)


@login_required
@tenant_access_required
def settlement_list(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    settlements = ListSettlementsUseCase.execute(ListSettlementsCommand(tenant_ctx=tenant_ctx))
    context = {"settlements": settlements, "tenant": request.tenant}
    return render(request, "dashboard/settlements/list.html", context)


@login_required
@tenant_access_required
def settlement_detail(request: HttpRequest, settlement_id: int) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    try:
        detail = GetSettlementDetailUseCase.execute(
            GetSettlementDetailCommand(settlement_id=settlement_id, store_id=tenant_ctx.store_id)
        )
    except SettlementNotFoundError:
        messages.error(request, "Settlement not found.")
        return redirect("settlements_web:dashboard_settlements_list")
    context = {"detail": detail, "tenant": request.tenant}
    return render(request, "dashboard/settlements/detail.html", context)


@staff_member_required
def admin_settlement_list(request: HttpRequest) -> HttpResponse:
    settlements = Settlement.objects.order_by("-created_at")
    context = {"settlements": settlements}
    return render(request, "admin/settlements/list.html", context)


@staff_member_required
def admin_settlement_detail(request: HttpRequest, settlement_id: int) -> HttpResponse:
    settlement = Settlement.objects.filter(id=settlement_id).first()
    if not settlement:
        messages.error(request, "Settlement not found.")
        return redirect("admin_settlements_list")
    items = SettlementItem.objects.filter(settlement_id=settlement.id).order_by("id")
    context = {"settlement": settlement, "items": items}
    return render(request, "admin/settlements/detail.html", context)


@staff_member_required
@require_POST
def admin_settlement_approve(request: HttpRequest, settlement_id: int) -> HttpResponse:
    try:
        ApproveSettlementUseCase.execute(
            ApproveSettlementCommand(settlement_id=settlement_id, actor_id=request.user.id)
        )
        messages.success(request, "Settlement approved.")
    except (SettlementNotFoundError, InvalidSettlementStateError) as exc:
        messages.error(request, str(exc))
    return redirect("admin_settlements_detail", settlement_id=settlement_id)


@staff_member_required
@require_POST
def admin_settlement_mark_paid(request: HttpRequest, settlement_id: int) -> HttpResponse:
    try:
        MarkSettlementPaidUseCase.execute(
            MarkSettlementPaidCommand(settlement_id=settlement_id, actor_id=request.user.id)
        )
        messages.success(request, "Settlement marked as paid.")
    except (SettlementNotFoundError, InvalidSettlementStateError) as exc:
        messages.error(request, str(exc))
    return redirect("admin_settlements_detail", settlement_id=settlement_id)

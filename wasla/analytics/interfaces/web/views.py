from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from analytics.application.assign_variant import AssignVariantCommand, AssignVariantUseCase
from analytics.application.report_kpis import ReportKpisCommand, ReportKpisUseCase
from analytics.models import Event, Experiment, ExperimentAssignment
from tenants.domain.tenant_context import TenantContext
from tenants.interfaces.web.decorators import tenant_access_required


def _build_tenant_context(request: HttpRequest) -> TenantContext:
    tenant = getattr(request, "tenant", None)
    tenant_id = getattr(tenant, "id", None)
    currency = getattr(tenant, "currency", "SAR")
    if not tenant_id:
        raise ValueError("Tenant context is required.")
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    user_id = request.user.id if request.user.is_authenticated else None
    return TenantContext(tenant_id=tenant_id, currency=currency, user_id=user_id, session_key=session_key)


@login_required
@tenant_access_required
@require_GET
def analytics_events(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    event_name = (request.GET.get("event_name") or "").strip()
    qs = Event.objects.filter(tenant_id=tenant_ctx.tenant_id).order_by("-occurred_at")
    if event_name:
        qs = qs.filter(event_name=event_name)
    events = qs[:200]
    kpis = ReportKpisUseCase.execute(ReportKpisCommand(tenant_ctx=tenant_ctx))
    return render(
        request,
        "dashboard/analytics/events.html",
        {"events": events, "event_name": event_name, "kpis": kpis},
    )


@login_required
@tenant_access_required
@require_GET
def analytics_experiments(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    experiments = Experiment.objects.filter(tenant_id__in=[None, tenant_ctx.tenant_id]).order_by("-created_at")
    return render(request, "dashboard/analytics/experiments.html", {"experiments": experiments})


@login_required
@tenant_access_required
@require_GET
def analytics_experiment_detail(request: HttpRequest, key: str) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    experiment = Experiment.objects.filter(key=key).first()
    if not experiment:
        return render(request, "dashboard/analytics/experiment_detail.html", {"experiment": None})
    assignments = (
        ExperimentAssignment.objects.filter(experiment=experiment, tenant_id=tenant_ctx.tenant_id)
        .values("variant")
        .order_by("variant")
    )
    return render(
        request,
        "dashboard/analytics/experiment_detail.html",
        {"experiment": experiment, "assignments": assignments},
    )

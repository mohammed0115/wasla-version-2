from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from imports.application.use_cases.create_import_job import (
    CreateImportJobCommand,
    CreateImportJobUseCase,
)
from imports.application.use_cases.get_import_job_status import (
    GetImportJobStatusCommand,
    GetImportJobStatusUseCase,
)
from imports.application.use_cases.run_import_job import RunImportJobCommand, RunImportJobUseCase
from imports.application.use_cases.validate_import_job import (
    ValidateImportJobCommand,
    ValidateImportJobUseCase,
)
from imports.domain.errors import ImportErrorBase
from imports.interfaces.web.forms import ImportStartForm
from imports.models import ImportJob, ImportRowError
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


@tenant_access_required
@require_GET
def import_index(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    form = ImportStartForm()
    jobs = ImportJob.objects.filter(store_id=tenant_ctx.tenant_id).order_by("-created_at")[:10]
    return render(request, "dashboard/import/index.html", {"form": form, "jobs": jobs})


@tenant_access_required
@require_POST
def import_start(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    form = ImportStartForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Invalid import file.")
        return redirect("web:dashboard_import")

    try:
        job = CreateImportJobUseCase.execute(
            CreateImportJobCommand(
                tenant_ctx=tenant_ctx,
                actor_id=request.user.id if request.user.is_authenticated else None,
                uploaded_file=form.cleaned_data["csv_file"],
                image_files=form.cleaned_data.get("images", []),
            )
        )
        ValidateImportJobUseCase.execute(ValidateImportJobCommand(import_job_id=job.id))
        RunImportJobUseCase.execute(RunImportJobCommand(import_job_id=job.id))
        messages.success(request, "Import completed.")
    except ImportErrorBase as exc:
        messages.error(request, str(exc))
        return redirect("web:dashboard_import")

    return redirect("web:dashboard_import_detail", job_id=job.id)


@tenant_access_required
@require_GET
def import_job_detail(request: HttpRequest, job_id: int) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    try:
        job = GetImportJobStatusUseCase.execute(
            GetImportJobStatusCommand(import_job_id=job_id, store_id=tenant_ctx.tenant_id)
        )
    except ImportErrorBase as exc:
        messages.error(request, str(exc))
        return redirect("web:dashboard_import")

    errors = ImportRowError.objects.filter(import_job=job).order_by("row_number")[:200]
    return render(
        request,
        "dashboard/import/job_detail.html",
        {"job": job, "errors": errors},
    )

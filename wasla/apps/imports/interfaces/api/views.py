from __future__ import annotations

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView

from apps.cart.interfaces.api.responses import api_response
from apps.imports.application.use_cases.create_import_job import (
    CreateImportJobCommand,
    CreateImportJobUseCase,
)
from apps.imports.application.use_cases.get_import_job_status import (
    GetImportJobStatusCommand,
    GetImportJobStatusUseCase,
)
from apps.imports.application.use_cases.run_import_job import RunImportJobCommand, RunImportJobUseCase
from apps.imports.application.use_cases.validate_import_job import (
    ValidateImportJobCommand,
    ValidateImportJobUseCase,
)
from apps.imports.domain.errors import ImportErrorBase
from apps.imports.models import ImportRowError
from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.guards import require_store, require_tenant


def _build_tenant_context(request) -> TenantContext:
    store = require_store(request)
    tenant = require_tenant(request)
    tenant_id = tenant.id
    store_id = store.id
    currency = getattr(tenant, "currency", "SAR")
    if not store_id:
        raise ValueError("Tenant context is required.")
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


class ImportStartAPI(APIView):
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "import"

    def post(self, request):
        tenant_ctx = _build_tenant_context(request)
        uploaded_file = request.FILES.get("csv_file")
        image_files = request.FILES.getlist("images")
        try:
            job = CreateImportJobUseCase.execute(
                CreateImportJobCommand(
                    tenant_ctx=tenant_ctx,
                    actor_id=request.user.id if request.user.is_authenticated else None,
                    uploaded_file=uploaded_file,
                    image_files=image_files,
                )
            )
            ValidateImportJobUseCase.execute(ValidateImportJobCommand(import_job_id=job.id))
            RunImportJobUseCase.execute(RunImportJobCommand(import_job_id=job.id))
        except ImportErrorBase as exc:
            return api_response(
                success=False,
                errors=[exc.message_key or str(exc)],
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return api_response(
            success=True,
            data={
                "job_id": job.id,
                "status": job.status,
                "total_rows": job.total_rows,
                "success_rows": job.success_rows,
                "failed_rows": job.failed_rows,
            },
        )


class ImportStatusAPI(APIView):
    def get(self, request, job_id: int):
        tenant_ctx = _build_tenant_context(request)
        try:
            job = GetImportJobStatusUseCase.execute(
                GetImportJobStatusCommand(import_job_id=job_id, store_id=tenant_ctx.store_id)
            )
        except ImportErrorBase as exc:
            return api_response(success=False, errors=[exc.message_key], status_code=status.HTTP_404_NOT_FOUND)

        errors = list(
            ImportRowError.objects.filter(import_job=job)
            .order_by("row_number")
            .values("row_number", "field", "message_key", "raw_value")
        )
        return api_response(
            success=True,
            data={
                "job_id": job.id,
                "status": job.status,
                "total_rows": job.total_rows,
                "success_rows": job.success_rows,
                "failed_rows": job.failed_rows,
                "errors": errors,
            },
        )

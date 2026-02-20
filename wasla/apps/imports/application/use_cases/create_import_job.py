from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.imports.domain.errors import ImportValidationError
from apps.imports.domain.policies import validate_csv_file
from apps.imports.infrastructure.storage import save_import_csv, save_import_images
from apps.imports.models import ImportJob
from apps.tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class CreateImportJobCommand:
    tenant_ctx: TenantContext
    actor_id: int | None
    uploaded_file: object
    image_files: list


class CreateImportJobUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: CreateImportJobCommand) -> ImportJob:
        if not cmd.tenant_ctx.store_id:
            raise ImportValidationError("Tenant context missing.", message_key="import.tenant.required")

        validate_csv_file(cmd.uploaded_file)

        job = ImportJob.objects.create(
            store_id=cmd.tenant_ctx.store_id,
            created_by_id=cmd.actor_id,
            status=ImportJob.STATUS_CREATED,
            source_type=ImportJob.SOURCE_CSV,
        )

        try:
            path = save_import_csv(store_id=cmd.tenant_ctx.store_id, job_id=job.id, uploaded_file=cmd.uploaded_file)
            save_import_images(
                store_id=cmd.tenant_ctx.store_id,
                job_id=job.id,
                image_files=cmd.image_files,
            )
            job.original_file_path = path
            job.save(update_fields=["original_file_path", "updated_at"])
        except Exception as exc:
            job.status = ImportJob.STATUS_FAILED
            job.errors_json = {"message_key": "import.file.save_failed"}
            job.save(update_fields=["status", "errors_json", "updated_at"])
            raise exc
        return job

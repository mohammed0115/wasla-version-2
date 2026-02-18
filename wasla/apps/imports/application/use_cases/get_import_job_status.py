from __future__ import annotations

from dataclasses import dataclass

from apps.imports.domain.errors import ImportJobNotFoundError
from apps.imports.models import ImportJob


@dataclass(frozen=True)
class GetImportJobStatusCommand:
    import_job_id: int
    store_id: int


class GetImportJobStatusUseCase:
    @staticmethod
    def execute(cmd: GetImportJobStatusCommand) -> ImportJob:
        job = ImportJob.objects.filter(id=cmd.import_job_id, store_id=cmd.store_id).first()
        if not job:
            raise ImportJobNotFoundError("Import job not found.", message_key="import.job.not_found")
        return job

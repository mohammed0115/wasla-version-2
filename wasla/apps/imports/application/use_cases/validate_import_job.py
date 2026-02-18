from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.catalog.models import Product
from apps.imports.domain.errors import ImportJobNotFoundError, ImportValidationError
from apps.imports.domain.policies import parse_decimal, parse_int, sanitize_text
from apps.imports.infrastructure.csv_utils import get_csv_headers, iter_csv_rows
from apps.imports.infrastructure.storage import list_import_images
from apps.imports.models import ImportJob, ImportRowError


REQUIRED_NAME_FIELDS = {"name_ar", "name_en", "name"}


@dataclass(frozen=True)
class ValidateImportJobCommand:
    import_job_id: int


class ValidateImportJobUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: ValidateImportJobCommand) -> ImportJob:
        job = ImportJob.objects.select_for_update().filter(id=cmd.import_job_id).first()
        if not job:
            raise ImportJobNotFoundError("Import job not found.", message_key="import.job.not_found")

        if not job.original_file_path:
            raise ImportValidationError("Import file missing.", message_key="import.csv.missing")

        ImportRowError.objects.filter(import_job=job).delete()
        job.status = ImportJob.STATUS_VALIDATING
        job.total_rows = 0
        job.success_rows = 0
        job.failed_rows = 0
        job.errors_json = {}
        job.save(update_fields=["status", "total_rows", "success_rows", "failed_rows", "errors_json", "updated_at"])

        headers = get_csv_headers(job.original_file_path)
        if not headers:
            job.status = ImportJob.STATUS_FAILED
            job.errors_json = {"message_key": "import.csv.empty"}
            job.save(update_fields=["status", "errors_json", "updated_at"])
            raise ImportValidationError("CSV is empty.", message_key="import.csv.empty")

        if "price" not in headers:
            job.status = ImportJob.STATUS_FAILED
            job.errors_json = {"message_key": "import.csv.missing_price"}
            job.save(update_fields=["status", "errors_json", "updated_at"])
            raise ImportValidationError("Missing price column.", message_key="import.csv.missing_price")

        if not headers.intersection(REQUIRED_NAME_FIELDS):
            job.status = ImportJob.STATUS_FAILED
            job.errors_json = {"message_key": "import.csv.missing_name"}
            job.save(update_fields=["status", "errors_json", "updated_at"])
            raise ImportValidationError("Missing name columns.", message_key="import.csv.missing_name")

        image_map = list_import_images(store_id=job.store_id, job_id=job.id)
        existing_skus = set(
            Product.objects.filter(store_id=job.store_id).values_list("sku", flat=True)
        )
        seen_skus: set[str] = set()

        failed_rows = 0
        total_rows = 0

        for row_number, row in iter_csv_rows(job.original_file_path):
            total_rows += 1
            row_errors = []
            name_ar = sanitize_text(row.get("name_ar", ""))
            name_en = sanitize_text(row.get("name_en", ""))
            name_raw = sanitize_text(row.get("name", ""))
            name = name_ar or name_en or name_raw
            if not name:
                row_errors.append(("name", "import.name.required", ""))
            if name and len(name) > 255:
                row_errors.append(("name", "import.name.too_long", name))

            try:
                price = parse_decimal(row.get("price", ""), field="price")
                if price <= 0:
                    raise ImportValidationError(
                        "Price must be positive.", message_key="import.price.positive", field="price"
                    )
            except ImportValidationError as exc:
                row_errors.append((exc.field or "price", exc.message_key, exc.raw_value))

            try:
                qty = parse_int(row.get("stock_quantity", ""), field="stock_quantity", default=0)
                if qty < 0:
                    raise ImportValidationError(
                        "Stock must be non-negative.",
                        message_key="import.stock.non_negative",
                        field="stock_quantity",
                    )
            except ImportValidationError as exc:
                row_errors.append((exc.field or "stock_quantity", exc.message_key, exc.raw_value))

            sku = sanitize_text(row.get("sku", ""))
            if sku:
                if len(sku) > 64:
                    row_errors.append(("sku", "import.sku.too_long", sku))
                if sku in existing_skus or sku in seen_skus:
                    row_errors.append(("sku", "import.sku.duplicate", sku))
                else:
                    seen_skus.add(sku)

            image_file = sanitize_text(row.get("image_file", "")) or sanitize_text(row.get("image_files", ""))
            image_url = sanitize_text(row.get("image_url", ""))
            if image_url:
                row_errors.append(("image_url", "import.image_url.unsupported", image_url))
            if image_file:
                if image_file not in image_map:
                    row_errors.append(("image_file", "import.image.missing", image_file))

            category_name = sanitize_text(row.get("category", ""))
            if category_name and len(category_name) > 255:
                row_errors.append(("category", "import.category.too_long", category_name))

            if row_errors:
                failed_rows += 1
                ImportRowError.objects.bulk_create(
                    [
                        ImportRowError(
                            import_job=job,
                            row_number=row_number,
                            field=field,
                            message_key=message_key,
                            raw_value=raw_value,
                        )
                        for field, message_key, raw_value in row_errors
                    ]
                )

        success_rows = max(total_rows - failed_rows, 0)
        job.total_rows = total_rows
        job.failed_rows = failed_rows
        job.success_rows = success_rows
        job.errors_json = {"failed_rows": failed_rows, "total_rows": total_rows}
        job.save(update_fields=["total_rows", "failed_rows", "success_rows", "errors_json", "updated_at"])
        return job

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.core.files import File
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Category, Inventory, Product
from apps.imports.domain.errors import ImportJobNotFoundError
from apps.imports.domain.policies import parse_decimal, parse_int, sanitize_text
from apps.imports.infrastructure.csv_utils import iter_csv_rows
from apps.imports.infrastructure.storage import list_import_images, open_import_file
from apps.imports.models import ImportJob, ImportRowError


@dataclass(frozen=True)
class RunImportJobCommand:
    import_job_id: int


class RunImportJobUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: RunImportJobCommand) -> ImportJob:
        job = ImportJob.objects.select_for_update().filter(id=cmd.import_job_id).first()
        if not job:
            raise ImportJobNotFoundError("Import job not found.", message_key="import.job.not_found")

        if job.status == ImportJob.STATUS_COMPLETED:
            return job

        if not job.original_file_path:
            job.status = ImportJob.STATUS_FAILED
            job.save(update_fields=["status", "updated_at"])
            return job

        job.status = ImportJob.STATUS_IMPORTING
        job.save(update_fields=["status", "updated_at"])

        image_map = list_import_images(store_id=job.store_id, job_id=job.id)
        error_rows = set(
            ImportRowError.objects.filter(import_job=job).values_list("row_number", flat=True)
        )
        existing_skus = set(
            Product.objects.filter(store_id=job.store_id).values_list("sku", flat=True)
        )
        created_rows = 0
        failed_rows = job.failed_rows

        category_cache: dict[str, Category] = {}

        for row_number, row in iter_csv_rows(job.original_file_path):
            if row_number in error_rows:
                continue

            try:
                with transaction.atomic():
                    name_ar = sanitize_text(row.get("name_ar", ""))
                    name_en = sanitize_text(row.get("name_en", ""))
                    name_raw = sanitize_text(row.get("name", ""))
                    name = name_ar or name_en or name_raw
                    if not name:
                        raise ValueError("Missing name.")

                    price = parse_decimal(row.get("price", ""), field="price")
                    stock_qty = parse_int(row.get("stock_quantity", ""), field="stock_quantity", default=0)
                    sku = sanitize_text(row.get("sku", ""))
                    if not sku:
                        sku = _generate_sku(name, existing_skus)
                    if sku in existing_skus:
                        raise ValueError("Duplicate SKU.")
                    existing_skus.add(sku)

                    product = Product(
                        store_id=job.store_id,
                        sku=sku,
                        name=name,
                        price=price,
                        is_active=True,
                    )

                    image_file = sanitize_text(row.get("image_file", "")) or sanitize_text(row.get("image_files", ""))
                    if image_file and image_file in image_map:
                        with open_import_file(image_map[image_file], "rb") as img:
                            product.image.save(image_file, File(img), save=False)

                    product.save()

                    category_name = sanitize_text(row.get("category", ""))
                    if category_name:
                        category = category_cache.get(category_name)
                        if not category:
                            category, _ = Category.objects.get_or_create(
                                store_id=job.store_id, name=category_name
                            )
                            category_cache[category_name] = category
                        product.categories.add(category)

                    Inventory.objects.create(
                        product=product,
                        quantity=stock_qty,
                        in_stock=stock_qty > 0,
                    )

                    created_rows += 1
            except Exception as exc:
                failed_rows += 1
                ImportRowError.objects.create(
                    import_job=job,
                    row_number=row_number,
                    field="row",
                    message_key="import.row.failed",
                    raw_value=str(exc),
                )

        job.success_rows = created_rows
        job.failed_rows = failed_rows
        job.status = ImportJob.STATUS_COMPLETED if created_rows > 0 else ImportJob.STATUS_FAILED
        job.save(update_fields=["success_rows", "failed_rows", "status", "updated_at"])
        return job


def _generate_sku(name: str, existing: Iterable[str]) -> str:
    base = slugify(name)[:40] or "item"
    candidate = base.upper()
    counter = 1
    while candidate in existing:
        counter += 1
        candidate = f"{base[:35]}-{counter}".upper()
    return candidate

from __future__ import annotations

import csv
import io

from apps.imports.domain.policies import sanitize_text
from apps.imports.infrastructure.storage import open_import_file


def normalize_header(header: str) -> str:
    return sanitize_text(header).lower().replace(" ", "_")


def iter_csv_rows(file_path: str):
    with open_import_file(file_path, "rb") as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig")
        reader = csv.DictReader(text)
        if not reader.fieldnames:
            return
        fieldnames = [normalize_header(h) for h in reader.fieldnames]
        original_names = list(reader.fieldnames)
        for index, row in enumerate(reader, start=2):
            normalized = {}
            for idx, original in enumerate(original_names):
                normalized[fieldnames[idx]] = row.get(original, "")
            yield index, normalized


def get_csv_headers(file_path: str) -> set[str]:
    with open_import_file(file_path, "rb") as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig")
        reader = csv.DictReader(text)
        if not reader.fieldnames:
            return set()
        return {normalize_header(h) for h in reader.fieldnames}

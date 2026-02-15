from __future__ import annotations

import os
from pathlib import Path

from django.core.files.storage import default_storage

from imports.domain.policies import sanitize_text, validate_image_file


def _safe_filename(filename: str) -> str:
    name = os.path.basename(filename or "")
    return sanitize_text(name).replace(" ", "_")


def save_import_csv(*, store_id: int, job_id: int, uploaded_file) -> str:
    filename = _safe_filename(uploaded_file.name or "import.csv") or "import.csv"
    path = f"imports/{store_id}/{job_id}/{filename}"
    if default_storage.exists(path):
        default_storage.delete(path)
    return default_storage.save(path, uploaded_file)


def save_import_images(*, store_id: int, job_id: int, image_files: list) -> list[str]:
    saved_paths = []
    for image_file in image_files or []:
        validate_image_file(image_file)
        filename = _safe_filename(image_file.name or "")
        if not filename:
            continue
        path = f"imports/{store_id}/{job_id}/images/{filename}"
        if default_storage.exists(path):
            default_storage.delete(path)
        saved_paths.append(default_storage.save(path, image_file))
    return saved_paths


def list_import_images(*, store_id: int, job_id: int) -> dict[str, str]:
    base_path = f"imports/{store_id}/{job_id}/images"
    if not default_storage.exists(base_path):
        return {}
    try:
        _, files = default_storage.listdir(base_path)
    except Exception:
        return {}
    mapping = {}
    for filename in files:
        mapping[filename] = f"{base_path}/{filename}"
    return mapping


def open_import_file(path: str, mode: str = "rb"):
    return default_storage.open(path, mode)

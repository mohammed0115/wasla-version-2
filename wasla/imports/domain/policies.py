from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .errors import ImportValidationError

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_CSV_EXTENSIONS = {".csv"}
MAX_CSV_SIZE_MB = 5
MAX_IMAGE_SIZE_MB = 5

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_text(value: str) -> str:
    cleaned = (value or "").strip()
    cleaned = _CONTROL_CHARS_RE.sub("", cleaned)
    return cleaned


def validate_csv_file(uploaded_file) -> None:
    if not uploaded_file:
        raise ImportValidationError("CSV file is required.", message_key="import.csv.required")

    ext = Path(uploaded_file.name or "").suffix.lower()
    if ext not in ALLOWED_CSV_EXTENSIONS:
        raise ImportValidationError("Invalid CSV file extension.", message_key="import.csv.invalid_extension")

    content_type = getattr(uploaded_file, "content_type", "") or ""
    if content_type and content_type not in {"text/csv", "application/vnd.ms-excel"}:
        raise ImportValidationError("Invalid CSV file type.", message_key="import.csv.invalid_type")

    max_bytes = MAX_CSV_SIZE_MB * 1024 * 1024
    if getattr(uploaded_file, "size", 0) > max_bytes:
        raise ImportValidationError("CSV file too large.", message_key="import.csv.too_large")


def validate_image_file(image_file) -> None:
    ext = Path(image_file.name or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ImportValidationError("Invalid image extension.", message_key="import.image.invalid_extension")
    content_type = getattr(image_file, "content_type", "") or ""
    if content_type and not content_type.startswith("image/"):
        raise ImportValidationError("Invalid image type.", message_key="import.image.invalid_type")
    max_bytes = MAX_IMAGE_SIZE_MB * 1024 * 1024
    if getattr(image_file, "size", 0) > max_bytes:
        raise ImportValidationError("Image file too large.", message_key="import.image.too_large")


def parse_decimal(value: str, *, field: str) -> Decimal:
    raw = sanitize_text(value)
    if raw == "":
        raise ImportValidationError("Missing value.", message_key="import.value.required", field=field, raw_value=value)
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        raise ImportValidationError("Invalid number.", message_key="import.value.invalid_number", field=field, raw_value=value)


def parse_int(value: str, *, field: str, default: int = 0) -> int:
    raw = sanitize_text(value)
    if raw == "":
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        raise ImportValidationError("Invalid integer.", message_key="import.value.invalid_integer", field=field, raw_value=value)


def validate_hex_color_optional(value: str, field: str) -> str:
    raw = sanitize_text(value)
    if not raw:
        return ""
    if not re.match(r"^#[0-9a-fA-F]{6}$", raw):
        raise ImportValidationError("Invalid color.", message_key="branding.invalid_color", field=field, raw_value=value)
    return raw.lower()

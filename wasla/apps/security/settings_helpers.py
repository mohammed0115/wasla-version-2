from __future__ import annotations

from django.utils.text import get_valid_filename


def sanitize_filename(name: str) -> str:
    cleaned = get_valid_filename(name or "").replace("..", "")
    cleaned = cleaned.replace("/", "").replace("\\", "")
    return cleaned or "file"

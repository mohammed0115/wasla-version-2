from __future__ import annotations

import re

from tenants.domain.policies import validate_hex_color


_FONT_RE = re.compile(r"^[a-zA-Z0-9\\s,'-]{0,80}$")


def validate_brand_colors(*, primary: str, secondary: str, accent: str) -> dict:
    return {
        "primary_color": validate_hex_color(primary),
        "secondary_color": validate_hex_color(secondary),
        "accent_color": validate_hex_color(accent),
    }


def validate_font_family(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if not _FONT_RE.match(value):
        raise ValueError("Invalid font family.")
    return value

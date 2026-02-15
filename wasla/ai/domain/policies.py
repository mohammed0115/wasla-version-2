from __future__ import annotations

import re

MAX_DESCRIPTION_CHARS = 600
SUPPORTED_LANGUAGES = {"ar", "en"}

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{6,}")
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_MAX_IMAGE_MB = 5
_BLOCKED_TERMS = {"password", "otp", "one-time", "credit card", "cvv", "iban", "ssn"}


def sanitize_prompt(text: str) -> str:
    raw = (text or "").strip()
    raw = _EMAIL_RE.sub("[redacted-email]", raw)
    raw = _PHONE_RE.sub("[redacted-phone]", raw)
    return raw


def is_prompt_allowed(text: str) -> bool:
    lowered = (text or "").lower()
    return not any(term in lowered for term in _BLOCKED_TERMS)


def normalize_language(lang: str) -> str:
    value = (lang or "").strip().lower()
    return value if value in SUPPORTED_LANGUAGES else "ar"


def build_description_prompt(*, name: str, attributes: dict, language: str) -> str:
    lang = normalize_language(language)
    attr_text = ", ".join([f"{k}: {v}" for k, v in (attributes or {}).items() if v])
    if lang == "ar":
        return (
            "اكتب وصفًا احترافيًا لمنتج تجارة إلكترونية باللهجة العربية الفصحى. "
            "لا تذكر أي بيانات شخصية. اجعل الوصف موجزًا ومقنعًا.\n"
            f"اسم المنتج: {name}\n"
            f"الخصائص: {attr_text}"
        )
    return (
        "Write a professional e-commerce product description. "
        "Do not include personal data. Keep it concise and persuasive.\n"
        f"Product name: {name}\n"
        f"Attributes: {attr_text}"
    )


def trim_description(text: str) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) > MAX_DESCRIPTION_CHARS:
        return cleaned[:MAX_DESCRIPTION_CHARS].rstrip()
    return cleaned


def validate_image_upload(image_file) -> None:
    if not image_file:
        raise ValueError("Image is required.")
    name = (getattr(image_file, "name", "") or "").lower()
    if not any(name.endswith(ext) for ext in _IMAGE_EXTENSIONS):
        raise ValueError("Invalid image type.")
    content_type = getattr(image_file, "content_type", "") or ""
    if content_type and not content_type.startswith("image/"):
        raise ValueError("Invalid image content type.")
    size = getattr(image_file, "size", 0)
    if size > _MAX_IMAGE_MB * 1024 * 1024:
        raise ValueError("Image too large.")

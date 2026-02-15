from __future__ import annotations

from django.core.validators import validate_email
from django.utils.text import slugify


def normalize_subject(subject: str) -> str:
    subject = (subject or "").strip()
    subject = subject.replace("\r", " ").replace("\n", " ").strip()
    return subject[:255]


def validate_recipient_email(email: str) -> str:
    email = (email or "").strip()
    validate_email(email)
    return email


def normalize_template_key(template_key: str) -> str:
    template_key = (template_key or "").strip()
    return slugify(template_key).replace("-", "_")[:80]


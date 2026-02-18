from __future__ import annotations

import re

from apps.notifications.domain.errors import EmailValidationError

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email_address(raw: str) -> str:
    email = (raw or "").strip().lower()
    if not email:
        raise EmailValidationError("Email is required.", field="email")
    if not EMAIL_REGEX.match(email):
        raise EmailValidationError("Email format is invalid.", field="email")
    return email


def validate_subject(raw: str) -> str:
    subject = (raw or "").strip()
    if not subject:
        raise EmailValidationError("Subject is required.", field="subject")
    if len(subject) > 200:
        raise EmailValidationError("Subject is too long.", field="subject")
    return subject


def validate_body(raw: str) -> str:
    body = (raw or "").strip()
    if not body:
        raise EmailValidationError("Body is required.", field="body")
    return body


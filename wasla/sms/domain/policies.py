from __future__ import annotations

import re

from sms.domain.errors import SmsValidationError

_NON_DIGITS = re.compile(r"\D+")


def validate_sms_body(raw: str) -> str:
    body = (raw or "").strip()
    if not body:
        raise SmsValidationError("Message body is required.", field="body")
    if len(body) > 1000:
        raise SmsValidationError("Message body is too long.", field="body")
    return body


def validate_sms_sender(raw: str) -> str:
    sender = (raw or "").strip()
    if not sender:
        raise SmsValidationError("Sender name is required.", field="sender")
    if len(sender) > 50:
        raise SmsValidationError("Sender name is too long.", field="sender")
    return sender


def normalize_recipient_phone(raw: str, *, default_country_code: str | None = None) -> str:
    """
    Normalize a phone number to E.164-like format (+<digits>).

    Accepts:
    - +9665xxxxxxx
    - 009665xxxxxxx
    - 9665xxxxxxx
    - 05xxxxxxx (with default_country_code="966")
    """

    text = (raw or "").strip()
    if not text:
        raise SmsValidationError("Recipient phone is required.", field="recipients")

    has_plus = text.startswith("+")
    digits = _NON_DIGITS.sub("", text)
    if not digits:
        raise SmsValidationError("Recipient phone is invalid.", field="recipients")

    if not has_plus and digits.startswith("00") and len(digits) > 2:
        digits = digits[2:]

    if default_country_code and not digits.startswith(default_country_code):
        digits = f"{default_country_code}{digits}"

    if len(digits) < 8 or len(digits) > 15:
        raise SmsValidationError("Recipient phone length is invalid.", field="recipients")

    return f"+{digits}"


def normalize_recipient_list(
    recipients: list[str] | tuple[str, ...],
    *,
    default_country_code: str | None = None,
) -> tuple[str, ...]:
    if not recipients:
        raise SmsValidationError("At least one recipient is required.", field="recipients")

    normalized: list[str] = []
    for recipient in recipients:
        normalized.append(normalize_recipient_phone(recipient, default_country_code=default_country_code))

    unique = tuple(dict.fromkeys(normalized).keys())
    if not unique:
        raise SmsValidationError("At least one recipient is required.", field="recipients")
    return unique


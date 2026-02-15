from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from notifications.domain.errors import EmailValidationError
from notifications.domain.policies import validate_email_address
from notifications.models import EmailOtp


@dataclass(frozen=True)
class VerifyEmailOtpCommand:
    email: str
    purpose: str
    code: str


@dataclass(frozen=True)
class VerifyEmailOtpResult:
    success: bool


class VerifyEmailOtpUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: VerifyEmailOtpCommand) -> VerifyEmailOtpResult:
        email = validate_email_address(cmd.email)
        code = (cmd.code or "").strip()
        if not code or len(code) < 4:
            raise EmailValidationError("Invalid code.", field="code")

        otp = (
            EmailOtp.objects.filter(email=email, purpose=cmd.purpose)
            .order_by("-created_at")
            .first()
        )
        if not otp:
            return VerifyEmailOtpResult(success=False)

        otp.attempts = otp.attempts + 1
        verified = otp.verify(code=code)
        if verified:
            otp.used_at = otp.used_at or timezone.now()
        otp.save(update_fields=["attempts", "used_at"])

        return VerifyEmailOtpResult(success=verified)

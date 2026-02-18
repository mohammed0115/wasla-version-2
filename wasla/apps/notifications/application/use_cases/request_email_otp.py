from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from apps.notifications.application.use_cases.send_email import SendEmailCommand, SendEmailUseCase
from apps.notifications.domain.policies import validate_email_address
from apps.notifications.models import EmailOtp


@dataclass(frozen=True)
class RequestEmailOtpCommand:
    email: str
    purpose: str
    ttl_minutes: int | None = None


@dataclass(frozen=True)
class RequestEmailOtpResult:
    otp_id: int
    expires_at: str


class RequestEmailOtpUseCase:
    @staticmethod
    def execute(cmd: RequestEmailOtpCommand) -> RequestEmailOtpResult:
        email = validate_email_address(cmd.email)
        ttl_minutes = cmd.ttl_minutes or getattr(settings, "EMAIL_OTP_TTL_MINUTES", 10)

        otp, code = EmailOtp.create_otp(email=email, purpose=cmd.purpose, ttl_minutes=ttl_minutes)

        subject = getattr(settings, "EMAIL_OTP_SUBJECT", "رمز التحقق")
        body = getattr(settings, "EMAIL_OTP_BODY", "رمز التحقق الخاص بك هو: {code}").format(code=code)

        SendEmailUseCase.execute(
            SendEmailCommand(
                subject=subject,
                body=body,
                to_email=email,
            )
        )

        return RequestEmailOtpResult(otp_id=otp.id, expires_at=otp.expires_at.isoformat())


import random
import time
from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.core.mail import send_mail

OTP_SESSION_KEY = "wasla_otp"
OTP_EMAIL_KEY = "wasla_otp_email"
OTP_EXPIRES_AT_KEY = "wasla_otp_expires_at"
OTP_PENDING_USER_ID = "wasla_pending_user_id"

DEFAULT_TTL_SECONDS = 10 * 60  # 10 minutes

@dataclass
class OtpResult:
    code: str
    expires_at: int

def generate_code() -> str:
    return f"{random.randint(0, 9999):04d}"

def store_otp(request, email: str, user_id: int, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> OtpResult:
    code = generate_code()
    expires_at = int(time.time()) + ttl_seconds
    request.session[OTP_SESSION_KEY] = code
    request.session[OTP_EMAIL_KEY] = email
    request.session[OTP_EXPIRES_AT_KEY] = expires_at
    request.session[OTP_PENDING_USER_ID] = user_id
    request.session.modified = True
    return OtpResult(code=code, expires_at=expires_at)

def validate_otp(request, code: str) -> bool:
    saved = request.session.get(OTP_SESSION_KEY)
    expires_at = request.session.get(OTP_EXPIRES_AT_KEY, 0)
    if not saved or int(time.time()) > int(expires_at):
        return False
    return str(saved) == str(code)

def clear_otp(request) -> None:
    for k in (OTP_SESSION_KEY, OTP_EMAIL_KEY, OTP_EXPIRES_AT_KEY, OTP_PENDING_USER_ID):
        if k in request.session:
            del request.session[k]
    request.session.modified = True

def send_otp_email(to_email: str, code: str) -> None:
    subject = "Wasla verification code"
    message = f"رمز التحقق الخاص بك في وصلة هو: {code}\n\nهذا الرمز صالح لمدة 10 دقائق. إذا لم تطلبه، تجاهل الرسالة."
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "Wasla <info@w-sala.com>"),
        recipient_list=[to_email],
        fail_silently=False,
    )
from __future__ import annotations

"""
Notifications models (MVP).

AR:
- يحتوي OTP عبر البريد (EmailOtp) مع hashing آمن والتحقق.
- يستخدم SECRET_KEY لتوليد HMAC (لا تخزن الكود بصيغته الأصلية).

EN:
- Contains email OTP (EmailOtp) with secure hashing and verification.
- Uses SECRET_KEY to compute HMAC (never stores the plain code).
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class EmailOtp(models.Model):
    """Email OTP record (hashed code) with TTL and limited attempts."""

    PURPOSE_LOGIN = "login"
    PURPOSE_REGISTER = "register"
    PURPOSE_RESET = "reset"
    PURPOSE_GENERIC = "generic"

    PURPOSE_CHOICES = [
        (PURPOSE_LOGIN, "Login"),
        (PURPOSE_REGISTER, "Register"),
        (PURPOSE_RESET, "Reset"),
        (PURPOSE_GENERIC, "Generic"),
    ]

    email = models.EmailField(db_index=True)
    purpose = models.CharField(max_length=32, choices=PURPOSE_CHOICES, default=PURPOSE_GENERIC)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["email", "purpose", "created_at"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"EmailOtp(email={self.email}, purpose={self.purpose}, expires_at={self.expires_at})"

    @staticmethod
    def generate_code(length: int = 6) -> str:
        digits = "0123456789"
        return "".join(secrets.choice(digits) for _ in range(length))

    @staticmethod
    def hash_code(*, email: str, purpose: str, code: str) -> str:
        secret = settings.SECRET_KEY.encode("utf-8")
        msg = f"{email}:{purpose}:{code}".encode("utf-8")
        return hmac.new(secret, msg, hashlib.sha256).hexdigest()

    @classmethod
    def create_otp(cls, *, email: str, purpose: str, ttl_minutes: int = 10) -> tuple["EmailOtp", str]:
        code = cls.generate_code()
        code_hash = cls.hash_code(email=email, purpose=purpose, code=code)
        expires_at = timezone.now() + timedelta(minutes=ttl_minutes)
        otp = cls.objects.create(email=email, purpose=purpose, code_hash=code_hash, expires_at=expires_at)
        return otp, code

    def verify(self, *, code: str) -> bool:
        if self.used_at is not None:
            return False
        if timezone.now() > self.expires_at:
            return False
        expected = self.hash_code(email=self.email, purpose=self.purpose, code=code)
        return hmac.compare_digest(expected, self.code_hash)

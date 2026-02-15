from __future__ import annotations

from unittest import mock

from django.test import TestCase

from notifications.application.use_cases.request_email_otp import RequestEmailOtpCommand, RequestEmailOtpUseCase
from notifications.application.use_cases.send_email import SendEmailCommand, SendEmailUseCase
from notifications.application.use_cases.verify_email_otp import VerifyEmailOtpCommand, VerifyEmailOtpUseCase
from notifications.models import EmailOtp
from emails.application.services.crypto import CredentialCrypto
from emails.models import GlobalEmailSettings


class EmailModuleTests(TestCase):
    def test_send_email_console(self):
        GlobalEmailSettings.objects.create(
            provider=GlobalEmailSettings.PROVIDER_SMTP,
            host="smtp.example.com",
            port=587,
            username="user@example.com",
            password_encrypted=CredentialCrypto.encrypt_text("secret"),
            from_email="no-reply@example.com",
            use_tls=True,
            enabled=True,
        )

        with mock.patch("smtplib.SMTP") as smtp_mock:
            SendEmailUseCase.execute(
                SendEmailCommand(
                    subject="Test",
                    body="Hello",
                    to_email="user@example.com",
                )
            )
            self.assertTrue(smtp_mock.called)

    def test_request_and_verify_otp(self):
        GlobalEmailSettings.objects.create(
            provider=GlobalEmailSettings.PROVIDER_SMTP,
            host="smtp.example.com",
            port=587,
            username="user@example.com",
            password_encrypted=CredentialCrypto.encrypt_text("secret"),
            from_email="no-reply@example.com",
            use_tls=True,
            enabled=True,
        )
        with mock.patch("smtplib.SMTP"):
            result = RequestEmailOtpUseCase.execute(
                RequestEmailOtpCommand(email="user@example.com", purpose=EmailOtp.PURPOSE_REGISTER)
            )
        self.assertIsNotNone(result.otp_id)

        otp = EmailOtp.objects.get(id=result.otp_id)
        self.assertIsNotNone(otp.expires_at)

        # Verify with wrong code
        bad = VerifyEmailOtpUseCase.execute(
            VerifyEmailOtpCommand(email="user@example.com", purpose=EmailOtp.PURPOSE_REGISTER, code="000000")
        )
        self.assertFalse(bad.success)

    def test_verify_otp_success(self):
        GlobalEmailSettings.objects.create(
            provider=GlobalEmailSettings.PROVIDER_SMTP,
            host="smtp.example.com",
            port=587,
            username="user@example.com",
            password_encrypted=CredentialCrypto.encrypt_text("secret"),
            from_email="no-reply@example.com",
            use_tls=True,
            enabled=True,
        )
        otp, code = EmailOtp.create_otp(email="user2@example.com", purpose=EmailOtp.PURPOSE_LOGIN, ttl_minutes=5)
        ok = VerifyEmailOtpUseCase.execute(
            VerifyEmailOtpCommand(email="user2@example.com", purpose=EmailOtp.PURPOSE_LOGIN, code=code)
        )
        self.assertTrue(ok.success)

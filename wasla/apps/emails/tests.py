from __future__ import annotations

from django.core import mail
from django.test import TestCase, override_settings

from apps.emails.application.services.crypto import CredentialCrypto
from apps.emails.application.use_cases.send_email import SendEmailCommand, SendEmailUseCase
from apps.emails.models import EmailLog, GlobalEmailSettings
# from tenants.models import Tenant


# class EmailGatewayTests(TestCase):
#     def setUp(self) -> None:
#         super().setUp()
#         self.tenant = Tenant.objects.create(slug="t1", name="T1", is_active=True, currency="SAR", language="ar")
#         GlobalEmailSettings.objects.create(
#             provider=GlobalEmailSettings.PROVIDER_SMTP,
#             host="smtp.example.com",
#             port=587,
#             username="user@example.com",
#             password_encrypted=CredentialCrypto.encrypt_text("secret"),
#             from_email="no-reply@example.com",
#             use_tls=True,
#             enabled=True,
#         )

#     @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
#     def test_send_email_is_idempotent(self):
#         self.assertEqual(len(mail.outbox), 0)
#         cmd = SendEmailCommand(
#             tenant_id=self.tenant.id,
#             to_email="user@example.com",
#             template_key="welcome",
#             context={"full_name": "User"},
#             idempotency_key="k1",
#         )
#         with self.captureOnCommitCallbacks(execute=True):
#             log1 = SendEmailUseCase.execute(cmd)
#         with self.captureOnCommitCallbacks(execute=True):
#             log2 = SendEmailUseCase.execute(cmd)
#         self.assertEqual(log1.id, log2.id)
#         self.assertEqual(EmailLog.objects.filter(tenant=self.tenant, idempotency_key="k1").count(), 1)
#         self.assertEqual(len(mail.outbox), 1)
# 
#     def test_credentials_crypto_requires_key_unless_plaintext_allowed(self):
#         token = CredentialCrypto.encrypt_text("x")
#         self.assertTrue(token.startswith("fernet:"))
#         self.assertEqual(CredentialCrypto.decrypt_text(token), "x")

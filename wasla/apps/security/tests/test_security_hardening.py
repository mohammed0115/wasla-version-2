from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from apps.security.models import SecurityAuditLog


class SecurityHardeningTests(TestCase):
    def setUp(self):
        self.User = get_user_model()

    def test_security_headers_are_applied(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertIn("Content-Security-Policy", response)

    @override_settings(
        SECURITY_RATE_LIMITS=[
            {
                "key": "payments_test",
                "pattern": r"^/api/payments/",
                "methods": ["POST"],
                "limit": 2,
                "window": 60,
                "message_key": "payments_rate_limited",
            }
        ]
    )
    def test_payment_endpoint_rate_limiting(self):
        r1 = self.client.post("/api/payments/initiate", data={})
        r2 = self.client.post("/api/payments/initiate", data={})
        r3 = self.client.post("/api/payments/initiate", data={})

        self.assertNotEqual(r1.status_code, 429)
        self.assertNotEqual(r2.status_code, 429)
        self.assertEqual(r3.status_code, 429)
        self.assertEqual(r3["Retry-After"], "60")

        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EVENT_RATE_LIMIT,
                outcome=SecurityAuditLog.OUTCOME_BLOCKED,
            ).exists()
        )

    @override_settings(
        ADMIN_PORTAL_2FA_ENABLED=True,
        ADMIN_PORTAL_2FA_TTL_SECONDS=300,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_admin_login_requires_2fa_and_logs(self):
        user = self.User.objects.create_user(
            username="portal_admin",
            email="portal_admin@test.local",
            password="StrongPass123!",
            is_staff=True,
        )

        resp = self.client.post(
            "/admin-portal/login/",
            {"username": "portal_admin", "password": "StrongPass123!"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Verification code")
        self.assertGreater(len(mail.outbox), 0)

        body = mail.outbox[-1].body
        match = re.search(r"(\d{6})", body)
        self.assertIsNotNone(match)
        otp_code = match.group(1)

        verify = self.client.post(
            "/admin-portal/login/",
            {"action": "verify_otp", "otp_code": otp_code},
        )
        self.assertEqual(verify.status_code, 302)
        self.assertTrue(verify["Location"].endswith("/admin-portal/"))

        self.assertTrue(
            SecurityAuditLog.objects.filter(
                user=user,
                event_type=SecurityAuditLog.EVENT_LOGIN,
                outcome=SecurityAuditLog.OUTCOME_SUCCESS,
            ).exists()
        )
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                user=user,
                event_type=SecurityAuditLog.EVENT_ADMIN_2FA,
                outcome=SecurityAuditLog.OUTCOME_SUCCESS,
            ).exists()
        )

    def test_payment_requests_are_audited(self):
        self.client.post("/api/payments/initiate", data={})
        self.assertTrue(
            SecurityAuditLog.objects.filter(event_type=SecurityAuditLog.EVENT_PAYMENT).exists()
        )

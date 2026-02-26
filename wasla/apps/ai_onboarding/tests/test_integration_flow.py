from django.test import TestCase, override_settings

from apps.accounts.services.otp import TEST_OTP_CODE


class OnboardingIntegrationFlowTests(TestCase):
    @override_settings(AI_ONBOARDING_RULES_ONLY=True)
    def test_register_to_provision_to_dashboard(self):
        register = self.client.post(
            "/auth/",
            data={
                "action": "register",
                "register-full_name": "Flow User",
                "register-email": "flow_user@example.com",
                "register-phone_country": "+966",
                "register-phone_number": "500000001",
                "register-password": "secret12345",
            },
        )
        self.assertEqual(register.status_code, 302)
        self.assertIn("/auth/verify/", register.url)

        otp = self.client.post("/auth/verify/", data={"otp_code": TEST_OTP_CODE})
        self.assertEqual(otp.status_code, 302)

        user = otp.wsgi_request.user
        self.client.force_login(user)

        analyze = self.client.post(
            "/api/onboarding/analyze/",
            data={
                "country": "SA",
                "language": "ar",
                "device_type": "web",
                "business_type": "fashion",
                "expected_products": 80,
                "expected_orders_per_day": 5,
            },
            content_type="application/json",
        )
        self.assertEqual(analyze.status_code, 200)
        profile_id = analyze.json()["data"]["profile_id"]

        provision = self.client.post(
            "/api/onboarding/provision/",
            data={"profile_id": profile_id, "idempotency_key": "flow-integration-0001"},
            content_type="application/json",
        )
        self.assertEqual(provision.status_code, 200)

        dashboard = self.client.get("/dashboard/")
        self.assertIn(dashboard.status_code, {200, 302})

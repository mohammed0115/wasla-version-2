import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.ai_onboarding.models import OnboardingProfile, ProvisioningRequest


class OnboardingAPITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="api_user",
            email="api_user@example.com",
            password="secret123",
        )
        self.client.force_login(self.user)

    @override_settings(AI_ONBOARDING_RULES_ONLY=True)
    def test_analyze_endpoint_returns_valid_decision(self):
        response = self.client.post(
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
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["recommended_plan_code"], "PRO")
        self.assertTrue(body["data"]["needs_variants"])
        self.assertIn("rationale", body["data"])

    @override_settings(AI_ONBOARDING_RULES_ONLY=True)
    def test_provision_endpoint_is_idempotent(self):
        analyze = self.client.post(
            "/api/onboarding/analyze/",
            data={
                "country": "SA",
                "language": "ar",
                "device_type": "web",
                "business_type": "fashion",
                "expected_products": 80,
            },
            content_type="application/json",
        )
        profile_id = analyze.json()["data"]["profile_id"]
        key = f"idem-{uuid.uuid4()}"

        first = self.client.post(
            "/api/onboarding/provision/",
            data={"profile_id": profile_id, "idempotency_key": key},
            content_type="application/json",
        )
        second = self.client.post(
            "/api/onboarding/provision/",
            data={"profile_id": profile_id, "idempotency_key": key},
            content_type="application/json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["data"]["store_id"], second.json()["data"]["store_id"])
        profile = OnboardingProfile.objects.get(id=profile_id)
        self.assertEqual(
            ProvisioningRequest.objects.filter(profile=profile, idempotency_key=key).count(),
            1,
        )

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.ai_onboarding.domain.analyzer import AnalyzeInput, BusinessAnalyzer


class AnalyzerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="analyzer_user",
            email="analyzer@example.com",
            password="secret123",
        )

    @override_settings(
        AI_ONBOARDING_RULES_ONLY=True,
        AI_ONBOARDING_LLM_ENABLED=True,
        OPENAI_API_KEY="dummy",
    )
    def test_rules_only_mode_disables_llm(self):
        decision = BusinessAnalyzer().analyze(
            AnalyzeInput(
                user=self.user,
                country="SA",
                language="ar",
                device_type="web",
                business_type="fashion",
                expected_products=80,
                expected_orders_per_day=5,
            )
        )
        self.assertFalse(decision.llm_used)
        self.assertEqual(decision.recommended_plan_code, "PRO")

    @override_settings(
        AI_ONBOARDING_RULES_ONLY=False,
        AI_ONBOARDING_LLM_ENABLED=True,
        OPENAI_API_KEY="dummy",
    )
    @patch("apps.ai_onboarding.infrastructure.llm_client.LLMClient.generate_recommendation")
    def test_llm_cannot_override_forbidden_fields(self, mock_llm):
        class FakeResult:
            rationale = "مبرر مختصر"
            suggested_categories = ["تصنيف 1", "تصنيف 2"]
            suggested_theme_key = "llm-theme"
            confidence = 87

        mock_llm.return_value = FakeResult()

        decision = BusinessAnalyzer().analyze(
            AnalyzeInput(
                user=self.user,
                country="SA",
                language="ar",
                device_type="web",
                business_type="fashion",
                expected_products=80,
                expected_orders_per_day=5,
            )
        )
        self.assertTrue(decision.llm_used)
        self.assertEqual(decision.recommended_plan_code, "PRO")
        self.assertTrue(decision.needs_variants)
        self.assertEqual(decision.recommended_theme_key, "llm-theme")

    @override_settings(
        AI_ONBOARDING_RULES_ONLY=False,
        AI_ONBOARDING_LLM_ENABLED=True,
        OPENAI_API_KEY="dummy",
    )
    @patch("apps.ai_onboarding.infrastructure.llm_client.LLMClient.generate_recommendation", side_effect=Exception("llm down"))
    def test_fallback_when_llm_fails(self, _mock_llm):
        decision = BusinessAnalyzer().analyze(
            AnalyzeInput(
                user=self.user,
                country="SA",
                language="ar",
                device_type="web",
                business_type="electronics",
                expected_products=70,
                expected_orders_per_day=4,
            )
        )
        self.assertFalse(decision.llm_used)
        self.assertIn(decision.recommended_plan_code, {"PRO", "ADVANCED"})

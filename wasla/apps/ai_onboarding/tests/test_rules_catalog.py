from django.test import TestCase

from apps.ai_onboarding.infrastructure.rules_catalog import RulesCatalog


class RulesCatalogTests(TestCase):
    def setUp(self):
        self.catalog = RulesCatalog()

    def test_fashion_rules_are_stable(self):
        out = self.catalog.evaluate(
            business_type="fashion",
            country="SA",
            expected_products=80,
            expected_orders_per_day=5,
        )
        self.assertTrue(out.needs_variants)
        self.assertEqual(out.recommended_plan_code, "PRO")
        self.assertIn("رجالي", out.categories)

    def test_grocery_prefers_advanced(self):
        out = self.catalog.evaluate(
            business_type="grocery",
            country="SA",
            expected_products=150,
            expected_orders_per_day=20,
        )
        self.assertEqual(out.recommended_plan_code, "ADVANCED")
        self.assertGreaterEqual(out.complexity_score, 80)

    def test_services_prefers_basic(self):
        out = self.catalog.evaluate(
            business_type="services",
            country="SA",
            expected_products=10,
            expected_orders_per_day=1,
        )
        self.assertEqual(out.recommended_plan_code, "BASIC")
        self.assertFalse(out.needs_variants)

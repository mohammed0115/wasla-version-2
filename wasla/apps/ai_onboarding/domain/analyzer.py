from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.db import transaction

from apps.ai_onboarding.infrastructure.llm_client import LLMClient, LLMClientError
from apps.ai_onboarding.infrastructure.rules_catalog import ALLOWED_PLAN_CODES, RulesCatalog
from apps.ai_onboarding.models import OnboardingDecision, OnboardingProfile
from apps.subscriptions.models import SubscriptionPlan


@dataclass(frozen=True)
class AnalyzeInput:
    user: object
    country: str
    language: str
    device_type: str
    business_type: str
    expected_products: int | None = None
    expected_orders_per_day: int | None = None
    store: object | None = None


@dataclass(frozen=True)
class OnboardingDecisionDTO:
    profile_id: int
    recommended_plan_code: str
    needs_variants: bool
    recommended_theme_key: str
    recommended_categories: list[str]
    shipping_profile: dict
    complexity_score: int
    rationale: str
    llm_used: bool
    llm_confidence: int


class BusinessAnalyzer:
    def __init__(self):
        self.rules = RulesCatalog()

    @transaction.atomic
    def analyze(self, profile_input: AnalyzeInput) -> OnboardingDecisionDTO:
        baseline = self.rules.evaluate(
            business_type=profile_input.business_type,
            country=profile_input.country,
            expected_products=profile_input.expected_products,
            expected_orders_per_day=profile_input.expected_orders_per_day,
        )

        llm_used = False
        llm_confidence = 0
        rationale = baseline.rationale_short
        recommended_categories = list(baseline.categories)
        recommended_theme_key = baseline.recommended_theme_key

        if self._can_use_llm():
            try:
                llm = LLMClient(
                    api_key=getattr(settings, "OPENAI_API_KEY", ""),
                    timeout_seconds=int(getattr(settings, "AI_ONBOARDING_LLM_TIMEOUT", 8)),
                    max_tokens=int(getattr(settings, "AI_ONBOARDING_LLM_MAX_TOKENS", 400)),
                    model=getattr(settings, "AI_ONBOARDING_LLM_MODEL", "gpt-5-mini"),
                )
                llm_result = llm.generate_recommendation(
                    business_type=profile_input.business_type,
                    country=profile_input.country,
                    language=profile_input.language,
                    baseline_decision={
                        "recommended_plan_code": baseline.recommended_plan_code,
                        "needs_variants": baseline.needs_variants,
                        "complexity_score": baseline.complexity_score,
                        "recommended_theme_key": baseline.recommended_theme_key,
                        "categories": baseline.categories,
                    },
                )
                rationale = llm_result.rationale
                if llm_result.suggested_categories:
                    recommended_categories = llm_result.suggested_categories[:10]
                if llm_result.suggested_theme_key:
                    recommended_theme_key = llm_result.suggested_theme_key
                llm_confidence = llm_result.confidence
                llm_used = True
            except LLMClientError:
                llm_used = False
                llm_confidence = 0

        profile = OnboardingProfile.objects.create(
            store=profile_input.store,
            user=profile_input.user,
            country=(profile_input.country or "SA").upper(),
            language=(profile_input.language or "ar").lower(),
            device_type=(profile_input.device_type or "web").lower(),
            business_type=self.rules.normalize_business_type(profile_input.business_type),
            expected_products=profile_input.expected_products,
            expected_orders_per_day=profile_input.expected_orders_per_day,
        )

        plan_fk = self._resolve_subscription_plan(baseline.recommended_plan_code)

        decision = OnboardingDecision.objects.create(
            profile=profile,
            recommended_plan=plan_fk,
            recommended_plan_code=baseline.recommended_plan_code,
            needs_variants=baseline.needs_variants,
            recommended_theme=recommended_theme_key,
            recommended_categories=recommended_categories,
            shipping_profile=baseline.shipping_profile,
            complexity_score=baseline.complexity_score,
            rationale=rationale,
            llm_used=llm_used,
            llm_confidence=llm_confidence,
        )

        return OnboardingDecisionDTO(
            profile_id=profile.id,
            recommended_plan_code=decision.recommended_plan_code,
            needs_variants=decision.needs_variants,
            recommended_theme_key=decision.recommended_theme,
            recommended_categories=list(decision.recommended_categories or []),
            shipping_profile=dict(decision.shipping_profile or {}),
            complexity_score=decision.complexity_score,
            rationale=decision.rationale,
            llm_used=decision.llm_used,
            llm_confidence=decision.llm_confidence,
        )

    @staticmethod
    def _can_use_llm() -> bool:
        if bool(getattr(settings, "AI_ONBOARDING_RULES_ONLY", False)):
            return False
        if not bool(getattr(settings, "AI_ONBOARDING_LLM_ENABLED", False)):
            return False
        api_key = (getattr(settings, "OPENAI_API_KEY", "") or "").strip()
        return bool(api_key)

    @staticmethod
    def _resolve_subscription_plan(plan_code: str) -> SubscriptionPlan | None:
        plan_code = (plan_code or "BASIC").upper()
        if plan_code not in ALLOWED_PLAN_CODES:
            plan_code = "BASIC"
        code_to_name = {
            "BASIC": ["basic"],
            "PRO": ["pro", "plus"],
            "ADVANCED": ["advanced", "enterprise", "pro"],
        }
        for candidate in code_to_name[plan_code]:
            found = SubscriptionPlan.objects.filter(name__iexact=candidate, is_active=True).order_by("price").first()
            if found:
                return found
        return SubscriptionPlan.objects.filter(is_active=True).order_by("price", "id").first()

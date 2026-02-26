from __future__ import annotations

from dataclasses import asdict, dataclass
import datetime
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.ai_onboarding.models import OnboardingDecision
from apps.catalog.models import Category
from apps.stores.models import Plan, Store, StoreSettings
from apps.subscriptions.models import StoreSubscription, SubscriptionPlan
from apps.tenants.application.use_cases.create_store import CreateStoreCommand, CreateStoreUseCase
from apps.tenants.models import StoreShippingSettings, Tenant, TenantMembership
from apps.tenants.services.audit_service import TenantAuditService
from apps.themes.models import StoreBranding


@dataclass(frozen=True)
class BusinessAnalysisResult:
    estimated_product_count: int
    needs_variants: bool
    recommended_plan: str
    recommended_theme: str
    recommended_categories: list[str]
    shipping_profile: str
    complexity_score: float


class BusinessAnalyzer:
    DEFAULT_RULES: dict[str, dict[str, Any]] = {
        "ملابس": {
            "estimated_product_count": 80,
            "needs_variants": True,
            "recommended_plan": "Pro",
            "recommended_theme": "fashion-premium",
            "recommended_categories": ["رجالي", "نسائي", "أطفال"],
            "shipping_profile": "advanced",
            "complexity_score": 0.82,
        },
        "electronics": {
            "estimated_product_count": 65,
            "needs_variants": True,
            "recommended_plan": "Pro",
            "recommended_theme": "tech-grid",
            "recommended_categories": ["هواتف", "لابتوب", "إكسسوارات"],
            "shipping_profile": "advanced",
            "complexity_score": 0.80,
        },
        "beauty": {
            "estimated_product_count": 45,
            "needs_variants": False,
            "recommended_plan": "Plus",
            "recommended_theme": "elegant-minimal",
            "recommended_categories": ["عناية", "مكياج", "عطور"],
            "shipping_profile": "standard",
            "complexity_score": 0.58,
        },
        "default": {
            "estimated_product_count": 30,
            "needs_variants": False,
            "recommended_plan": "Basic",
            "recommended_theme": "default",
            "recommended_categories": ["منتجات عامة"],
            "shipping_profile": "standard",
            "complexity_score": 0.45,
        },
    }

    def __init__(self, rules: dict[str, dict[str, Any]] | None = None):
        self.rules = rules or getattr(settings, "AI_ONBOARDING_RULES", None) or self.DEFAULT_RULES

    def analyze(
        self,
        *,
        business_type: str,
        country: str,
        language: str,
        device_type: str,
    ) -> BusinessAnalysisResult:
        normalized_business = (business_type or "").strip().lower()
        normalized_country = (country or "").strip().upper()
        normalized_language = (language or "").strip().lower()
        normalized_device = (device_type or "desktop").strip().lower()

        rule = self.rules.get(normalized_business) or self.rules.get(business_type) or self.rules["default"]
        data = dict(rule)

        data = self._apply_ai_placeholder_adjustments(
            base=data,
            country=normalized_country,
            language=normalized_language,
            device_type=normalized_device,
        )

        return BusinessAnalysisResult(
            estimated_product_count=max(1, int(data["estimated_product_count"])),
            needs_variants=bool(data["needs_variants"]),
            recommended_plan=str(data["recommended_plan"]),
            recommended_theme=str(data["recommended_theme"]),
            recommended_categories=list(data["recommended_categories"]),
            shipping_profile=str(data["shipping_profile"]),
            complexity_score=float(data["complexity_score"]),
        )

    @staticmethod
    def _apply_ai_placeholder_adjustments(
        *,
        base: dict[str, Any],
        country: str,
        language: str,
        device_type: str,
    ) -> dict[str, Any]:
        adjusted = dict(base)
        product_count = int(adjusted.get("estimated_product_count") or 0)
        complexity = float(adjusted.get("complexity_score") or 0)

        if country in {"SA", "AE", "EG"}:
            product_count = int(round(product_count * 1.12))
            complexity += 0.04

        if language.startswith("ar"):
            complexity += 0.02

        if device_type == "mobile":
            product_count = int(round(product_count * 1.08))

        if product_count >= 70 and adjusted.get("recommended_plan") == "Plus":
            adjusted["recommended_plan"] = "Pro"

        adjusted["estimated_product_count"] = product_count
        adjusted["complexity_score"] = min(0.99, max(0.1, round(complexity, 2)))
        return adjusted


class RecommendationEngine:
    def explain_plan_choice(self, *, business_type: str, analysis: BusinessAnalysisResult) -> str:
        return (
            f"Based on business type '{business_type}', expected catalog size "
            f"({analysis.estimated_product_count}), and complexity score "
            f"({analysis.complexity_score}), {analysis.recommended_plan} is the best starting plan."
        )

    def estimate_revenue_range(self, *, analysis: BusinessAnalysisResult) -> dict[str, int]:
        multiplier = 140 if analysis.needs_variants else 90
        low = int(analysis.estimated_product_count * multiplier)
        high = int(low * 2.4)
        return {"monthly_low_sar": low, "monthly_high_sar": high}

    def calculate_feature_needs(self, *, analysis: BusinessAnalysisResult) -> list[str]:
        features = ["catalog", "checkout", "analytics_basic"]
        if analysis.needs_variants:
            features.append("variants")
        if analysis.shipping_profile == "advanced":
            features.append("shipping_advanced")
        if analysis.recommended_plan.lower() == "pro":
            features.extend(["ai_tools", "priority_support"])
        return sorted(set(features))


@dataclass(frozen=True)
class ProvisioningResult:
    tenant_id: int
    store_id: int
    recommended_plan: str
    features_enabled: list[str]
    categories_created: list[str]
    decision_id: int


class ProvisioningEngine:
    def __init__(self):
        self.recommendation_engine = RecommendationEngine()

    @transaction.atomic
    def provision(
        self,
        *,
        user,
        business_type: str,
        analysis: BusinessAnalysisResult,
        tenant: Tenant | None = None,
        store_name: str | None = None,
        store_slug: str | None = None,
    ) -> ProvisioningResult:
        tenant = tenant or self._ensure_tenant(user=user, store_name=store_name, store_slug=store_slug)
        store = self._ensure_store(user=user, tenant=tenant, analysis=analysis, business_type=business_type)

        chosen_subscription_plan = self._resolve_subscription_plan(analysis.recommended_plan)
        chosen_legacy_plan = self._resolve_legacy_plan(analysis.recommended_plan)

        features = self.recommendation_engine.calculate_feature_needs(analysis=analysis)
        categories = self._ensure_categories(store_id=tenant.id, category_names=analysis.recommended_categories)

        self._upsert_subscription(tenant=tenant, subscription_plan=chosen_subscription_plan)
        self._apply_store_plan_and_theme(store=store, legacy_plan=chosen_legacy_plan, analysis=analysis)
        self._configure_store_features(store=store, features=features, needs_variants=analysis.needs_variants)
        self._configure_shipping_defaults(tenant=tenant, shipping_profile=analysis.shipping_profile)

        decision_payload = {
            "analysis": asdict(analysis),
            "feature_needs": features,
            "plan_reason": self.recommendation_engine.explain_plan_choice(
                business_type=business_type,
                analysis=analysis,
            ),
            "estimated_revenue": self.recommendation_engine.estimate_revenue_range(analysis=analysis),
            "provisioned_at": timezone.now().isoformat(),
        }

        decision, _ = OnboardingDecision.objects.update_or_create(
            store=store,
            defaults={
                "business_type": business_type,
                "recommended_plan": analysis.recommended_plan,
                "complexity_score": Decimal(str(round(analysis.complexity_score, 2))),
                "decision_payload": decision_payload,
            },
        )

        TenantAuditService.record_action(
            tenant,
            "ai_onboarding_provisioned",
            actor=getattr(user, "username", "system"),
            details="AI onboarding provisioning completed.",
            metadata={
                "store_id": store.id,
                "recommended_plan": analysis.recommended_plan,
                "features": features,
                "categories": categories,
                "complexity_score": analysis.complexity_score,
            },
        )

        return ProvisioningResult(
            tenant_id=tenant.id,
            store_id=store.id,
            recommended_plan=analysis.recommended_plan,
            features_enabled=features,
            categories_created=categories,
            decision_id=decision.id,
        )

    @staticmethod
    def _ensure_tenant(*, user, store_name: str | None, store_slug: str | None) -> Tenant:
        owned_tenant = Tenant.objects.filter(
            memberships__user=user,
            memberships__role=TenantMembership.ROLE_OWNER,
            memberships__is_active=True,
        ).first()
        if owned_tenant:
            return owned_tenant

        default_name = (store_name or getattr(user, "first_name", "") or "My Store").strip()
        base_slug = store_slug or slugify(default_name) or slugify(getattr(user, "username", "") or "store") or "store"
        command = CreateStoreCommand(
            user=user,
            name=default_name,
            slug=base_slug,
            currency="SAR",
            language="ar",
        )
        result = CreateStoreUseCase.execute(command)
        return result.tenant

    @staticmethod
    def _ensure_store(*, user, tenant: Tenant, analysis: BusinessAnalysisResult, business_type: str) -> Store:
        store = Store.objects.filter(tenant=tenant).order_by("id").first()
        if store:
            return store

        base_name = tenant.name or getattr(user, "username", "Store")
        base_slug = tenant.slug or slugify(base_name) or f"store-{tenant.id}"

        store = Store.objects.create(
            owner=user,
            tenant=tenant,
            name=base_name,
            slug=base_slug,
            subdomain=tenant.slug or base_slug,
            status=Store.STATUS_ACTIVE,
            category=(business_type or "").strip(),
            country="SA",
            theme_name=analysis.recommended_theme,
        )
        return store

    @staticmethod
    def _resolve_subscription_plan(recommended_plan: str) -> SubscriptionPlan:
        by_name = SubscriptionPlan.objects.filter(name__iexact=recommended_plan, is_active=True).first()
        if by_name:
            return by_name
        fallback = SubscriptionPlan.objects.filter(is_active=True).order_by("price", "id").first()
        if fallback:
            return fallback
        return SubscriptionPlan.objects.create(
            name=recommended_plan,
            price=0,
            billing_cycle="monthly",
            features=[],
            is_active=True,
        )

    @staticmethod
    def _resolve_legacy_plan(recommended_plan: str) -> Plan | None:
        legacy = Plan.objects.filter(name__iexact=recommended_plan).first()
        if legacy:
            return legacy
        return Plan.objects.order_by("price_monthly", "id").first()

    @staticmethod
    def _ensure_categories(*, store_id: int, category_names: list[str]) -> list[str]:
        created_or_existing: list[str] = []
        for name in category_names:
            normalized = (name or "").strip()
            if not normalized:
                continue
            category, _ = Category.objects.get_or_create(store_id=store_id, name=normalized)
            created_or_existing.append(category.name)
        return created_or_existing

    @staticmethod
    def _upsert_subscription(*, tenant: Tenant, subscription_plan: SubscriptionPlan) -> None:
        cycle_days = 365 if subscription_plan.billing_cycle == "yearly" else 30
        now_date = timezone.now().date()
        StoreSubscription.objects.update_or_create(
            store_id=tenant.id,
            defaults={
                "plan": subscription_plan,
                "status": "active" if float(subscription_plan.price or 0) <= 0 else "active",
                "start_date": now_date,
                "end_date": now_date + datetime.timedelta(days=cycle_days),
            },
        )

    @staticmethod
    def _apply_store_plan_and_theme(*, store: Store, legacy_plan: Plan | None, analysis: BusinessAnalysisResult) -> None:
        update_fields: list[str] = []
        if legacy_plan and store.plan_id != legacy_plan.id:
            store.plan = legacy_plan
            update_fields.append("plan")
        if store.theme_name != analysis.recommended_theme:
            store.theme_name = analysis.recommended_theme
            update_fields.append("theme_name")
        if update_fields:
            store.save(update_fields=update_fields + ["updated_at"])

        StoreBranding.objects.update_or_create(
            store_id=store.id,
            defaults={
                "theme_code": analysis.recommended_theme,
            },
        )

    @staticmethod
    def _configure_store_features(*, store: Store, features: list[str], needs_variants: bool) -> None:
        settings_obj, _ = StoreSettings.objects.get_or_create(store=store)
        metadata = dict(settings_obj.metadata_json or {})
        metadata.setdefault("enabled_features", [])
        metadata["enabled_features"] = sorted(set(metadata["enabled_features"] + list(features)))
        metadata["variants_enabled"] = bool(needs_variants)
        settings_obj.metadata_json = metadata
        settings_obj.save(update_fields=["metadata_json", "updated_at"])

    @staticmethod
    def _configure_shipping_defaults(*, tenant: Tenant, shipping_profile: str) -> None:
        if shipping_profile == "advanced":
            mode = StoreShippingSettings.MODE_MANUAL_DELIVERY
            delivery_fee_flat = Decimal("18.00")
            free_shipping_threshold = Decimal("350.00")
        else:
            mode = StoreShippingSettings.MODE_PICKUP
            delivery_fee_flat = Decimal("0.00")
            free_shipping_threshold = None

        StoreShippingSettings.objects.update_or_create(
            tenant=tenant,
            defaults={
                "fulfillment_mode": mode,
                "origin_city": "Riyadh",
                "delivery_fee_flat": delivery_fee_flat,
                "free_shipping_threshold": free_shipping_threshold,
                "is_enabled": True,
            },
        )

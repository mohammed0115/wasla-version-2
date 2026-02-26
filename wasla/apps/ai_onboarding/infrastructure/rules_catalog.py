from __future__ import annotations

from dataclasses import dataclass


ALLOWED_PLAN_CODES = {"BASIC", "PRO", "ADVANCED"}
ALLOWED_BUSINESS_TYPES = {
    "fashion",
    "electronics",
    "cosmetics",
    "grocery",
    "general",
    "services",
}
GCC_COUNTRIES = {"SA", "AE", "KW", "QA", "BH", "OM"}


@dataclass(frozen=True)
class RuleOutput:
    estimated_product_count: int
    needs_variants: bool
    recommended_plan_code: str
    recommended_theme_key: str
    categories: list[str]
    shipping_profile: dict
    complexity_score: int
    rationale_short: str


class RulesCatalog:
    def normalize_business_type(self, business_type: str) -> str:
        value = (business_type or "general").strip().lower()
        aliases = {
            "ملابس": "fashion",
            "موضة": "fashion",
            "electronics": "electronics",
            "الكترونيات": "electronics",
            "cosmetics": "cosmetics",
            "تجميل": "cosmetics",
            "grocery": "grocery",
            "بقالة": "grocery",
            "خدمات": "services",
            "services": "services",
            "عام": "general",
            "general": "general",
        }
        normalized = aliases.get(value, value)
        if normalized not in ALLOWED_BUSINESS_TYPES:
            return "general"
        return normalized

    def evaluate(
        self,
        *,
        business_type: str,
        country: str,
        expected_products: int | None,
        expected_orders_per_day: int | None,
    ) -> RuleOutput:
        btype = self.normalize_business_type(business_type)
        country_code = (country or "SA").strip().upper()
        in_gcc = country_code in GCC_COUNTRIES

        baseline = self._baseline_for_business(btype)

        estimated_products = expected_products if expected_products and expected_products > 0 else baseline["estimated_product_count"]
        complexity = baseline["complexity_score"]
        plan_code = baseline["recommended_plan_code"]

        if expected_orders_per_day and expected_orders_per_day >= 20:
            complexity += 10
            if plan_code == "BASIC":
                plan_code = "PRO"
        elif expected_orders_per_day and expected_orders_per_day >= 8:
            complexity += 5

        if estimated_products >= 200:
            complexity += 15
            plan_code = "ADVANCED"
        elif estimated_products >= 90 and plan_code == "BASIC":
            plan_code = "PRO"

        if in_gcc:
            complexity += 4
            baseline_shipping = dict(baseline["shipping_profile"])
            baseline_shipping["region"] = "GCC"
        else:
            baseline_shipping = dict(baseline["shipping_profile"])
            baseline_shipping["region"] = "INTL"

        complexity = max(0, min(100, complexity))
        if plan_code not in ALLOWED_PLAN_CODES:
            plan_code = "BASIC"

        return RuleOutput(
            estimated_product_count=estimated_products,
            needs_variants=bool(baseline["needs_variants"]),
            recommended_plan_code=plan_code,
            recommended_theme_key=baseline["recommended_theme_key"],
            categories=list(baseline["categories"]),
            shipping_profile=baseline_shipping,
            complexity_score=complexity,
            rationale_short=baseline["rationale_short"],
        )

    @staticmethod
    def _baseline_for_business(business_type: str) -> dict:
        baselines = {
            "fashion": {
                "estimated_product_count": 80,
                "needs_variants": True,
                "recommended_plan_code": "PRO",
                "recommended_theme_key": "fashion-premium",
                "categories": ["رجالي", "نسائي", "أطفال", "إكسسوارات"],
                "shipping_profile": {
                    "mode": "standard_plus",
                    "insurance": False,
                    "same_day": False,
                    "free_shipping_threshold": 299,
                },
                "complexity_score": 72,
                "rationale_short": "قطاع الأزياء يحتاج إدارة مقاسات ومتغيرات مع باقة قوية للنمو.",
            },
            "electronics": {
                "estimated_product_count": 60,
                "needs_variants": False,
                "recommended_plan_code": "PRO",
                "recommended_theme_key": "tech-grid",
                "categories": ["هواتف", "لابتوبات", "ملحقات", "منزل ذكي"],
                "shipping_profile": {
                    "mode": "insured",
                    "insurance": True,
                    "same_day": False,
                    "free_shipping_threshold": 499,
                },
                "complexity_score": 74,
                "rationale_short": "الإلكترونيات تحتاج شحن مؤمن وتتبع دقيق مع إمكانيات تشغيلية أعلى.",
            },
            "cosmetics": {
                "estimated_product_count": 45,
                "needs_variants": False,
                "recommended_plan_code": "PRO",
                "recommended_theme_key": "beauty-elegant",
                "categories": ["عناية بالبشرة", "مكياج", "عطور", "عناية بالشعر"],
                "shipping_profile": {
                    "mode": "standard",
                    "insurance": False,
                    "same_day": False,
                    "free_shipping_threshold": 249,
                },
                "complexity_score": 64,
                "rationale_short": "التجميل يحتاج عرض بصري منظم وتسويق مستمر، وباقة PRO مناسبة للبداية.",
            },
            "grocery": {
                "estimated_product_count": 120,
                "needs_variants": False,
                "recommended_plan_code": "ADVANCED",
                "recommended_theme_key": "grocery-fast",
                "categories": ["خضار وفواكه", "ألبان", "مخبوزات", "مواد أساسية"],
                "shipping_profile": {
                    "mode": "express",
                    "insurance": False,
                    "same_day": True,
                    "cold_chain": True,
                    "free_shipping_threshold": 199,
                },
                "complexity_score": 82,
                "rationale_short": "البقالة تعتمد على سرعة التسليم وكثافة الطلبات اليومية لذا يلزم إعداد متقدم.",
            },
            "services": {
                "estimated_product_count": 20,
                "needs_variants": False,
                "recommended_plan_code": "BASIC",
                "recommended_theme_key": "services-clean",
                "categories": ["استشارات", "حجوزات", "باقات", "عقود"],
                "shipping_profile": {
                    "mode": "none",
                    "insurance": False,
                    "same_day": False,
                },
                "complexity_score": 35,
                "rationale_short": "نشاط الخدمات لا يعتمد على شحن أو متغيرات كثيرة، لذا باقة BASIC كافية.",
            },
            "general": {
                "estimated_product_count": 35,
                "needs_variants": False,
                "recommended_plan_code": "BASIC",
                "recommended_theme_key": "default",
                "categories": ["منتجات مميزة", "عروض", "الجديد"],
                "shipping_profile": {
                    "mode": "standard",
                    "insurance": False,
                    "same_day": False,
                    "free_shipping_threshold": 299,
                },
                "complexity_score": 50,
                "rationale_short": "تم اختيار إعداد متوازن كبداية مع قابلية التوسع عند نمو المتجر.",
            },
        }
        return baselines.get(business_type, baselines["general"])

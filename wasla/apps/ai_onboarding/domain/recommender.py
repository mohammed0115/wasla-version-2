from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanReasoning:
    text: str
    product_range_hint: str


class RecommendationEngine:
    def explain_plan_choice(self, *, business_type: str, plan_code: str, complexity_score: int) -> PlanReasoning:
        if plan_code == "ADVANCED":
            product_hint = "كتالوج واسع وطلبات متكررة"
        elif plan_code == "PRO":
            product_hint = "نمو متوسط إلى مرتفع"
        else:
            product_hint = "بداية خفيفة"

        text = (
            f"بناءً على نشاط {business_type} وتعقيد تشغيلي {complexity_score}/100، "
            f"نوصي بخطة {plan_code} كبداية مناسبة للسوق السعودي."
        )
        return PlanReasoning(text=text, product_range_hint=product_hint)

    def estimate_revenue_range(self, *, expected_products: int, expected_orders_per_day: int | None) -> dict:
        orders = expected_orders_per_day if expected_orders_per_day and expected_orders_per_day > 0 else max(1, expected_products // 20)
        low = orders * 75 * 30
        high = orders * 220 * 30
        return {
            "monthly_low_sar": int(low),
            "monthly_high_sar": int(high),
            "note": "تقدير تقريبي غير ملزم يعتمد على متوسطات السوق.",
        }

    def calculate_feature_needs(self, *, needs_variants: bool, shipping_profile: dict, complexity_score: int) -> list[str]:
        features = ["catalog", "orders", "analytics"]
        if needs_variants:
            features.append("variants")
        if shipping_profile.get("mode") in {"insured", "express", "standard_plus"}:
            features.append("shipping_advanced")
        if complexity_score >= 70:
            features.append("automation")
        return sorted(set(features))

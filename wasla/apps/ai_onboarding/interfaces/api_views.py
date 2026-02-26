from __future__ import annotations

from django.http import HttpRequest
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.ai_onboarding.domain.analyzer import AnalyzeInput, BusinessAnalyzer
from apps.ai_onboarding.domain.provisioner import ProvisioningEngine
from apps.ai_onboarding.models import OnboardingProfile
from apps.cart.interfaces.api.responses import api_response


class OnboardingAnalyzeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: HttpRequest):
        try:
            expected_products = int(request.data.get("expected_products")) if request.data.get("expected_products") not in (None, "") else None
        except (TypeError, ValueError):
            return api_response(success=False, errors=["expected_products must be integer"], status_code=status.HTTP_400_BAD_REQUEST)

        try:
            expected_orders_per_day = int(request.data.get("expected_orders_per_day")) if request.data.get("expected_orders_per_day") not in (None, "") else None
        except (TypeError, ValueError):
            return api_response(success=False, errors=["expected_orders_per_day must be integer"], status_code=status.HTTP_400_BAD_REQUEST)

        business_type = (request.data.get("business_type") or "").strip()
        if not business_type:
            return api_response(success=False, errors=["business_type is required"], status_code=status.HTTP_400_BAD_REQUEST)

        analyzer = BusinessAnalyzer()
        decision = analyzer.analyze(
            AnalyzeInput(
                user=request.user,
                country=(request.data.get("country") or "SA").strip(),
                language=(request.data.get("language") or "ar").strip(),
                device_type=(request.data.get("device_type") or "web").strip(),
                business_type=business_type,
                expected_products=expected_products,
                expected_orders_per_day=expected_orders_per_day,
            )
        )

        return api_response(
            success=True,
            data={
                "profile_id": decision.profile_id,
                "recommended_plan_code": decision.recommended_plan_code,
                "needs_variants": decision.needs_variants,
                "recommended_theme_key": decision.recommended_theme_key,
                "recommended_categories": decision.recommended_categories,
                "shipping_profile": decision.shipping_profile,
                "complexity_score": decision.complexity_score,
                "rationale": decision.rationale,
                "llm_used": decision.llm_used,
                "llm_confidence": decision.llm_confidence,
            },
            status_code=status.HTTP_200_OK,
        )


class OnboardingProvisionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: HttpRequest):
        profile_id = request.data.get("profile_id")
        idempotency_key = (request.data.get("idempotency_key") or "").strip()

        if not profile_id:
            return api_response(success=False, errors=["profile_id is required"], status_code=status.HTTP_400_BAD_REQUEST)
        if not idempotency_key:
            return api_response(success=False, errors=["idempotency_key is required"], status_code=status.HTTP_400_BAD_REQUEST)

        try:
            profile = OnboardingProfile.objects.get(id=profile_id)
        except OnboardingProfile.DoesNotExist:
            return api_response(success=False, errors=["profile not found"], status_code=status.HTTP_404_NOT_FOUND)

        if profile.user_id != request.user.id:
            return api_response(success=False, errors=["forbidden"], status_code=status.HTTP_403_FORBIDDEN)

        try:
            result = ProvisioningEngine().provision(
                profile_id=profile.id,
                idempotency_key=idempotency_key,
                actor_user=request.user,
            )
        except PermissionError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_400_BAD_REQUEST)

        return api_response(
            success=True,
            data={"store_id": result.store_id, "next_url": result.next_url},
            status_code=status.HTTP_200_OK,
        )

from __future__ import annotations

from dataclasses import asdict

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.ai_onboarding.services import BusinessAnalyzer, ProvisioningEngine, RecommendationEngine
from apps.cart.interfaces.api.responses import api_response
from apps.tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from apps.tenants.domain.errors import StoreAccessDeniedError
from apps.tenants.models import Tenant


class OnboardingAnalyzeAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        business_type = (request.data.get("business_type") or "").strip()
        country = (request.data.get("country") or "SA").strip()
        language = (request.data.get("language") or "ar").strip()
        device_type = (request.data.get("device_type") or "desktop").strip()

        if not business_type:
            return api_response(
                success=False,
                errors=["business_type is required"],
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        analyzer = BusinessAnalyzer()
        recommender = RecommendationEngine()
        analysis = analyzer.analyze(
            business_type=business_type,
            country=country,
            language=language,
            device_type=device_type,
        )
        feature_needs = recommender.calculate_feature_needs(analysis=analysis)

        return api_response(
            success=True,
            data={
                **asdict(analysis),
                "plan_explanation": recommender.explain_plan_choice(
                    business_type=business_type,
                    analysis=analysis,
                ),
                "estimated_revenue_range": recommender.estimate_revenue_range(analysis=analysis),
                "feature_needs": feature_needs,
            },
            status_code=status.HTTP_200_OK,
        )


class OnboardingProvisionAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        business_type = (request.data.get("business_type") or "").strip()
        country = (request.data.get("country") or "SA").strip()
        language = (request.data.get("language") or "ar").strip()
        device_type = (request.data.get("device_type") or "desktop").strip()
        tenant_id = request.data.get("tenant_id")
        store_name = (request.data.get("store_name") or "").strip() or None
        store_slug = (request.data.get("store_slug") or "").strip() or None

        if not business_type:
            return api_response(
                success=False,
                errors=["business_type is required"],
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        tenant = None
        if tenant_id:
            tenant = get_object_or_404(Tenant, id=tenant_id)
            try:
                EnsureTenantOwnershipPolicy.ensure_is_owner(user=request.user, tenant=tenant)
            except StoreAccessDeniedError as exc:
                return api_response(
                    success=False,
                    errors=[str(exc)],
                    status_code=status.HTTP_403_FORBIDDEN,
                )

        analyzer = BusinessAnalyzer()
        analysis = analyzer.analyze(
            business_type=business_type,
            country=country,
            language=language,
            device_type=device_type,
        )

        provisioner = ProvisioningEngine()
        result = provisioner.provision(
            user=request.user,
            business_type=business_type,
            analysis=analysis,
            tenant=tenant,
            store_name=store_name,
            store_slug=store_slug,
        )

        return api_response(
            success=True,
            data={
                "tenant_id": result.tenant_id,
                "store_id": result.store_id,
                "recommended_plan": result.recommended_plan,
                "features_enabled": result.features_enabled,
                "categories_created": result.categories_created,
                "decision_id": result.decision_id,
            },
            status_code=status.HTTP_200_OK,
        )

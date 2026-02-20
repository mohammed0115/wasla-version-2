from __future__ import annotations

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView

from apps.ai.application.use_cases.apply_category import ApplyCategoryCommand, ApplyCategoryUseCase
from apps.ai.application.use_cases.categorize_product import (
    CategorizeProductCommand,
    CategorizeProductUseCase,
)
from apps.ai.application.use_cases.generate_description import (
    GenerateProductDescriptionCommand,
    GenerateProductDescriptionUseCase,
)
from apps.ai.application.use_cases.index_product_embeddings import (
    IndexProductEmbeddingsCommand,
    IndexProductEmbeddingsUseCase,
)
from apps.ai.application.use_cases.save_description import (
    SaveProductDescriptionCommand,
    SaveProductDescriptionUseCase,
)
from apps.ai.application.use_cases.visual_search import VisualSearchCommand, VisualSearchUseCase
from apps.cart.interfaces.api.responses import api_response
from apps.subscriptions.application.services.feature_gate import FeatureGateService
from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.guards import require_store, require_tenant

from .throttles import TenantScopedRateThrottle


def _build_tenant_context(request) -> TenantContext:
    store = require_store(request)
    tenant = require_tenant(request)
    tenant_id = tenant.id
    store_id = store.id
    currency = getattr(tenant, "currency", "SAR")
    if not store_id:
        raise ValueError("Tenant context is required.")
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    user_id = request.user.id if request.user.is_authenticated else None
    return TenantContext(
        tenant_id=tenant_id,
        store_id=store_id,
        currency=currency,
        user_id=user_id,
        session_key=session_key,
    )


def _feature_denied_response(feature_key: str):
    return api_response(
        success=False,
        errors=["feature_not_allowed"],
        data={"feature": feature_key},
        status_code=status.HTTP_403_FORBIDDEN,
    )


def _to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value):
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in ("1", "true", "yes", "on"):
        return True
    if normalized in ("0", "false", "no", "off"):
        return False
    return None


class AIDescriptionAPI(APIView):
    throttle_classes = [TenantScopedRateThrottle]
    throttle_scope = "ai"

    def post(self, request):
        tenant_ctx = _build_tenant_context(request)
        if not FeatureGateService.can_use_feature(tenant_ctx.store_id, FeatureGateService.AI_TOOLS):
            return _feature_denied_response(FeatureGateService.AI_TOOLS)

        try:
            product_id = int(request.data.get("product_id") or 0)
        except (TypeError, ValueError):
            return api_response(
                success=False,
                errors=["invalid_product_id"],
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        language = (request.data.get("language") or "ar").strip().lower() or "ar"
        action = (request.data.get("action") or "generate").strip().lower()

        if action == "save":
            description = request.data.get("description") or ""
            force = (request.data.get("force") or "").strip().lower() in ("1", "true", "yes", "on")
            result = SaveProductDescriptionUseCase.execute(
                SaveProductDescriptionCommand(
                    tenant_ctx=tenant_ctx,
                    actor_id=request.user.id if request.user.is_authenticated else None,
                    product_id=product_id,
                    language=language,
                    description=description,
                    force=force,
                )
            )
            if not result.product:
                return api_response(
                    success=False,
                    errors=["product_not_found"],
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            if not result.saved:
                return api_response(
                    success=False,
                    errors=[result.reason or "already_exists"],
                    status_code=status.HTTP_409_CONFLICT,
                )
            return api_response(success=True, data={"saved": True, "product_id": product_id})

        result = GenerateProductDescriptionUseCase.execute(
            GenerateProductDescriptionCommand(
                tenant_ctx=tenant_ctx,
                actor_id=request.user.id if request.user.is_authenticated else None,
                product_id=product_id,
                language=language,
            )
        )
        return api_response(
            success=True,
            data={
                "description": result.description,
                "language": result.language,
                "provider": result.provider,
                "token_count": result.token_count,
                "warnings": result.warnings,
                "query_attributes": getattr(result, "query_attributes", None),
                "fallback_reason": result.fallback_reason,
            },
        )


class AICategorizeAPI(APIView):
    throttle_classes = [TenantScopedRateThrottle]
    throttle_scope = "ai"

    def post(self, request):
        tenant_ctx = _build_tenant_context(request)
        if not FeatureGateService.can_use_feature(tenant_ctx.store_id, FeatureGateService.AI_TOOLS):
            return _feature_denied_response(FeatureGateService.AI_TOOLS)

        try:
            product_id = int(request.data.get("product_id") or 0)
        except (TypeError, ValueError):
            return api_response(
                success=False,
                errors=["invalid_product_id"],
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        action = (request.data.get("action") or "suggest").strip().lower()
        if action == "apply":
            try:
                category_id = int(request.data.get("category_id") or 0)
            except (TypeError, ValueError):
                return api_response(
                    success=False,
                    errors=["invalid_category_id"],
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            ok = ApplyCategoryUseCase.execute(
                ApplyCategoryCommand(
                    tenant_ctx=tenant_ctx,
                    actor_id=request.user.id if request.user.is_authenticated else None,
                    product_id=product_id,
                    category_id=category_id,
                )
            )
            if not ok:
                return api_response(
                    success=False,
                    errors=["apply_failed"],
                    status_code=status.HTTP_409_CONFLICT,
                )
            return api_response(success=True, data={"applied": True})

        result = CategorizeProductUseCase.execute(
            CategorizeProductCommand(
                tenant_ctx=tenant_ctx,
                actor_id=request.user.id if request.user.is_authenticated else None,
                product_id=product_id,
            )
        )
        return api_response(
            success=True,
            data={
                "category_id": result.category_id,
                "category_name": result.category_name,
                "confidence": result.confidence,
                "provider": result.provider,
                "warnings": result.warnings,
                "query_attributes": getattr(result, "query_attributes", None),
                "fallback_reason": result.fallback_reason,
            },
        )


class AIVisualSearchAPI(APIView):
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [TenantScopedRateThrottle]
    throttle_scope = "ai"

    def post(self, request):
        tenant_ctx = _build_tenant_context(request)
        if not FeatureGateService.can_use_feature(tenant_ctx.store_id, FeatureGateService.AI_VISUAL_SEARCH):
            return _feature_denied_response(FeatureGateService.AI_VISUAL_SEARCH)

        image_file = request.FILES.get("image")
        try:
            top_n = int(request.data.get("top_n") or 12)
        except (TypeError, ValueError):
            top_n = 12
        top_n = max(1, min(top_n, 24))
        result = VisualSearchUseCase.execute(
            VisualSearchCommand(
                tenant_ctx=tenant_ctx,
                image_file=image_file,
                top_n=top_n,
                price_min=_to_float(request.data.get("price_min")),
                price_max=_to_float(request.data.get("price_max")),
                color=(request.data.get("color") or "").strip().lower() or None,
                brightness=(request.data.get("brightness") or "").strip().lower() or None,
                category=(request.data.get("category") or "").strip().lower() or None,
                material=(request.data.get("material") or "").strip().lower() or None,
                style=(request.data.get("style") or "").strip().lower() or None,
                white_background=_to_bool(request.data.get("white_background")),
            )
        )
        return api_response(
            success=True,
            data={
                "results": result.results,
                "provider": result.provider,
                "warnings": result.warnings,
                "query_attributes": getattr(result, "query_attributes", None),
                "fallback_reason": result.fallback_reason,
            },
        )


class AIIndexProductsAPI(APIView):
    """Index product images into vector store for the current tenant."""

    throttle_classes = [TenantScopedRateThrottle]
    throttle_scope = "ai"
    parser_classes = [FormParser, MultiPartParser]

    def post(self, request):
        tenant_ctx = _build_tenant_context(request)
        if not FeatureGateService.can_use_feature(tenant_ctx.store_id, FeatureGateService.AI_TOOLS):
            return _feature_denied_response(FeatureGateService.AI_TOOLS)

        product_ids = request.data.get("product_ids")
        force = str(request.data.get("force", "false")).lower() in ("1", "true", "yes")

        if product_ids:
            if isinstance(product_ids, str):
                ids = [int(x) for x in product_ids.split(",") if x.strip().isdigit()]
            elif isinstance(product_ids, list):
                ids = [int(x) for x in product_ids if str(x).isdigit()]
            else:
                ids = None
        else:
            ids = None

        result = IndexProductEmbeddingsUseCase.execute(
            IndexProductEmbeddingsCommand(tenant_ctx=tenant_ctx, product_ids=ids, force=force)
        )
        return api_response(result, status_code=status.HTTP_200_OK)

from __future__ import annotations

from rest_framework import status
from rest_framework.views import APIView

from apps.analytics.application.assign_variant import AssignVariantCommand, AssignVariantUseCase
from apps.analytics.application.recommend_products import RecommendProductsCommand, RecommendProductsUseCase
from apps.analytics.application.score_transaction import ScoreTransactionCommand, ScoreTransactionUseCase
from apps.analytics.application.track_event import TrackEventCommand, TrackEventUseCase
from apps.analytics.domain.types import EventDTO
from apps.cart.interfaces.api.responses import api_response
from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.guards import require_store, require_tenant


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


class TrackEventAPI(APIView):
    def post(self, request):
        tenant_ctx = _build_tenant_context(request)
        data = request.data
        event = EventDTO(
            event_name=str(data.get("event_name") or "").strip(),
            actor_type=str(data.get("actor_type") or "").strip().upper() or ("CUSTOMER" if request.user.is_authenticated else "ANON"),
            actor_id=request.user.id if request.user.is_authenticated else None,
            session_key=request.session.session_key,
            object_type=data.get("object_type"),
            object_id=data.get("object_id"),
            properties=data.get("properties") or {},
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            ip_address=request.META.get("REMOTE_ADDR", ""),
        )
        try:
            TrackEventUseCase.execute(TrackEventCommand(tenant_id=tenant_ctx.store_id, event=event))
        except Exception as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_400_BAD_REQUEST)
        return api_response(success=True, data={"tracked": True})


class ExperimentAssignmentAPI(APIView):
    def get(self, request, key: str):
        tenant_ctx = _build_tenant_context(request)
        result = AssignVariantUseCase.execute(
            AssignVariantCommand(
                tenant_ctx=tenant_ctx,
                experiment_key=key,
                actor_id=request.user.id if request.user.is_authenticated else None,
                session_key=request.session.session_key,
            )
        )
        return api_response(
            success=True,
            data={"experiment": result.experiment_key, "variant": result.variant, "assigned": result.assigned},
        )


class RecommendationsAPI(APIView):
    def get(self, request):
        tenant_ctx = _build_tenant_context(request)
        context = request.query_params.get("context") or "HOME"
        object_id = request.query_params.get("object_id")
        snapshot = RecommendProductsUseCase.execute(
            RecommendProductsCommand(
                tenant_ctx=tenant_ctx,
                context=context,
                object_id=object_id,
            )
        )
        return api_response(
            success=True,
            data={
                "context": snapshot.context,
                "object_id": snapshot.object_id,
                "recommended_ids": snapshot.recommended_ids_json,
                "strategy": snapshot.strategy,
            },
        )


class RiskAssessmentAPI(APIView):
    def get(self, request, order_id: int):
        tenant_ctx = _build_tenant_context(request)
        result = ScoreTransactionUseCase.execute(
            ScoreTransactionCommand(
                tenant_ctx=tenant_ctx,
                order_id=order_id,
            )
        )
        return api_response(
            success=True,
            data={
                "order_id": result.order_id,
                "score": result.score,
                "level": result.level,
                "reasons": result.reasons,
            },
        )

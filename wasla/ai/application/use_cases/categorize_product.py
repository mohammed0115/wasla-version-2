from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from ai.application.use_cases.log_ai_request import LogAIRequestCommand, LogAIRequestUseCase
from ai.domain.policies import is_prompt_allowed
from ai.domain.types import CategoryResult
from ai.infrastructure.providers.registry import get_provider
from catalog.models import Category, Product
from tenants.domain.tenant_context import TenantContext
from analytics.application.telemetry import TelemetryService
from analytics.domain.types import ActorContext, ObjectRef


@dataclass(frozen=True)
class CategorizeProductCommand:
    tenant_ctx: TenantContext
    actor_id: int | None
    product_id: int


class CategorizeProductUseCase:
    @staticmethod
    def execute(cmd: CategorizeProductCommand) -> CategoryResult:
        product = Product.objects.filter(id=cmd.product_id, store_id=cmd.tenant_ctx.tenant_id).first()
        if not product:
            TelemetryService.track(
                event_name="ai.categorization_suggested",
                tenant_ctx=cmd.tenant_ctx,
                actor_ctx=ActorContext(
                    actor_type="MERCHANT",
                    actor_id=cmd.actor_id,
                    session_key=cmd.tenant_ctx.session_key,
                ),
                object_ref=ObjectRef(object_type="PRODUCT", object_id=cmd.product_id),
                properties={"status": "failed", "reason_code": "product_not_found"},
            )
            return CategoryResult(
                category_id=None,
                category_name=None,
                confidence=0,
                provider="",
                warnings=["product_not_found"],
                fallback_reason="product_not_found",
            )

        categories = list(Category.objects.filter(store_id=cmd.tenant_ctx.tenant_id).order_by("name"))
        if not categories:
            TelemetryService.track(
                event_name="ai.categorization_suggested",
                tenant_ctx=cmd.tenant_ctx,
                actor_ctx=ActorContext(
                    actor_type="MERCHANT",
                    actor_id=cmd.actor_id,
                    session_key=cmd.tenant_ctx.session_key,
                ),
                object_ref=ObjectRef(object_type="PRODUCT", object_id=product.id),
                properties={"status": "failed", "reason_code": "no_categories"},
            )
            return CategoryResult(
                category_id=None,
                category_name=None,
                confidence=0,
                provider="",
                warnings=["no_categories"],
                fallback_reason="no_categories",
            )

        labels = [c.name for c in categories]
        if not is_prompt_allowed(product.name):
            LogAIRequestUseCase.execute(
                LogAIRequestCommand(
                    store_id=cmd.tenant_ctx.tenant_id,
                    feature="CATEGORY",
                    provider="",
                    latency_ms=0,
                    token_count=None,
                    cost_estimate=0,
                    status="FAILED",
                )
            )
            TelemetryService.track(
                event_name="ai.categorization_suggested",
                tenant_ctx=cmd.tenant_ctx,
                actor_ctx=ActorContext(
                    actor_type="MERCHANT",
                    actor_id=cmd.actor_id,
                    session_key=cmd.tenant_ctx.session_key,
                ),
                object_ref=ObjectRef(object_type="PRODUCT", object_id=product.id),
                properties={"status": "failed", "reason_code": "content_blocked"},
            )
            return CategoryResult(
                category_id=None,
                category_name=None,
                confidence=0,
                provider="",
                warnings=["content_blocked"],
                fallback_reason="content_blocked",
            )
        provider = get_provider()
        started = monotonic()
        try:
            result = provider.classify_text(text=product.name, labels=labels)
            match = next((c for c in categories if c.name == result.label), None)
            LogAIRequestUseCase.execute(
                LogAIRequestCommand(
                    store_id=cmd.tenant_ctx.tenant_id,
                    feature="CATEGORY",
                    provider=result.provider,
                    latency_ms=int((monotonic() - started) * 1000),
                    token_count=None,
                    cost_estimate=0,
                    status="SUCCESS",
                )
            )
            TelemetryService.track(
                event_name="ai.categorization_suggested",
                tenant_ctx=cmd.tenant_ctx,
                actor_ctx=ActorContext(
                    actor_type="MERCHANT",
                    actor_id=cmd.actor_id,
                    session_key=cmd.tenant_ctx.session_key,
                ),
                object_ref=ObjectRef(object_type="PRODUCT", object_id=product.id),
                properties={
                    "status": "success",
                    "provider_code": result.provider,
                    "confidence": result.confidence,
                },
            )
            return CategoryResult(
                category_id=match.id if match else None,
                category_name=result.label,
                confidence=result.confidence,
                provider=result.provider,
                warnings=[],
            )
        except Exception:
            LogAIRequestUseCase.execute(
                LogAIRequestCommand(
                    store_id=cmd.tenant_ctx.tenant_id,
                    feature="CATEGORY",
                    provider=getattr(provider, "code", ""),
                    latency_ms=int((monotonic() - started) * 1000),
                    token_count=None,
                    cost_estimate=0,
                    status="FAILED",
                )
            )
            fallback = categories[0]
            TelemetryService.track(
                event_name="ai.categorization_suggested",
                tenant_ctx=cmd.tenant_ctx,
                actor_ctx=ActorContext(
                    actor_type="MERCHANT",
                    actor_id=cmd.actor_id,
                    session_key=cmd.tenant_ctx.session_key,
                ),
                object_ref=ObjectRef(object_type="PRODUCT", object_id=product.id),
                properties={
                    "status": "failed",
                    "provider_code": getattr(provider, "code", ""),
                    "reason_code": "provider_failed",
                },
            )
            return CategoryResult(
                category_id=fallback.id,
                category_name=fallback.name,
                confidence=0.3,
                provider=getattr(provider, "code", ""),
                warnings=["fallback_used"],
                fallback_reason="provider_failed",
            )

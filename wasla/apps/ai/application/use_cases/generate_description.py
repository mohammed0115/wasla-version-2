from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from apps.ai.application.use_cases.log_ai_request import LogAIRequestCommand, LogAIRequestUseCase
from apps.ai.domain.policies import (
    build_description_prompt,
    is_prompt_allowed,
    normalize_language,
    sanitize_prompt,
    trim_description,
)
from apps.ai.domain.types import DescriptionResult
from apps.ai.infrastructure.providers.registry import get_provider
from apps.catalog.models import Product
from apps.tenants.domain.tenant_context import TenantContext
from apps.analytics.application.telemetry import TelemetryService
from apps.analytics.domain.types import ActorContext, ObjectRef


@dataclass(frozen=True)
class GenerateProductDescriptionCommand:
    tenant_ctx: TenantContext
    actor_id: int | None
    product_id: int
    language: str


class GenerateProductDescriptionUseCase:
    @staticmethod
    def execute(cmd: GenerateProductDescriptionCommand) -> DescriptionResult:
        product = Product.objects.filter(id=cmd.product_id, store_id=cmd.tenant_ctx.tenant_id).first()
        if not product:
            return DescriptionResult(
                description="",
                language=normalize_language(cmd.language),
                provider="",
                token_count=None,
                warnings=["product_not_found"],
                fallback_reason="product_not_found",
            )

        attributes = {
            "price": str(product.price),
            "sku": product.sku,
        }
        language = normalize_language(cmd.language)
        safe_name = sanitize_prompt(product.name)
        if not is_prompt_allowed(safe_name):
            LogAIRequestUseCase.execute(
                LogAIRequestCommand(
                    store_id=cmd.tenant_ctx.tenant_id,
                    feature="DESCRIPTION",
                    provider="",
                    latency_ms=0,
                    token_count=None,
                    cost_estimate=0,
                    status="FAILED",
                )
            )
            TelemetryService.track(
                event_name="ai.description_generated",
                tenant_ctx=cmd.tenant_ctx,
                actor_ctx=ActorContext(
                    actor_type="MERCHANT",
                    actor_id=cmd.actor_id,
                    session_key=cmd.tenant_ctx.session_key,
                ),
                object_ref=ObjectRef(object_type="PRODUCT", object_id=product.id),
                properties={"language": language, "status": "failed", "reason_code": "content_blocked"},
            )
            return DescriptionResult(
                description=product.name,
                language=language,
                provider="",
                token_count=None,
                warnings=["content_blocked"],
                fallback_reason="content_blocked",
            )
        prompt = build_description_prompt(
            name=safe_name,
            attributes=attributes,
            language=language,
        )
        provider = get_provider()
        started = monotonic()
        warnings: list[str] = []

        try:
            result = provider.generate_text(prompt=prompt, language=language, max_tokens=240)
            description = trim_description(result.text)
            if len(description) < len(result.text):
                warnings.append("description_trimmed")
            LogAIRequestUseCase.execute(
                LogAIRequestCommand(
                    store_id=cmd.tenant_ctx.tenant_id,
                    feature="DESCRIPTION",
                    provider=result.provider,
                    latency_ms=int((monotonic() - started) * 1000),
                    token_count=result.token_count,
                    cost_estimate=0,
                    status="SUCCESS",
                )
            )
            TelemetryService.track(
                event_name="ai.description_generated",
                tenant_ctx=cmd.tenant_ctx,
                actor_ctx=ActorContext(
                    actor_type="MERCHANT",
                    actor_id=cmd.actor_id,
                    session_key=cmd.tenant_ctx.session_key,
                ),
                object_ref=ObjectRef(object_type="PRODUCT", object_id=product.id),
                properties={"provider_code": result.provider, "language": language, "status": "success"},
            )
            return DescriptionResult(
                description=description,
                language=language,
                provider=result.provider,
                token_count=result.token_count,
                warnings=warnings,
            )
        except Exception:
            LogAIRequestUseCase.execute(
                LogAIRequestCommand(
                    store_id=cmd.tenant_ctx.tenant_id,
                    feature="DESCRIPTION",
                    provider=getattr(provider, "code", ""),
                    latency_ms=int((monotonic() - started) * 1000),
                    token_count=None,
                    cost_estimate=0,
                    status="FAILED",
                )
            )
            fallback_text = f"{product.name} - {product.price} {cmd.tenant_ctx.currency}"
            TelemetryService.track(
                event_name="ai.description_generated",
                tenant_ctx=cmd.tenant_ctx,
                actor_ctx=ActorContext(
                    actor_type="MERCHANT",
                    actor_id=cmd.actor_id,
                    session_key=cmd.tenant_ctx.session_key,
                ),
                object_ref=ObjectRef(object_type="PRODUCT", object_id=product.id),
                properties={
                    "provider_code": getattr(provider, "code", ""),
                    "language": language,
                    "status": "failed",
                    "reason_code": "provider_failed",
                },
            )
            return DescriptionResult(
                description=fallback_text,
                language=language,
                provider=getattr(provider, "code", ""),
                token_count=None,
                warnings=["fallback_used"],
                fallback_reason="provider_failed",
            )

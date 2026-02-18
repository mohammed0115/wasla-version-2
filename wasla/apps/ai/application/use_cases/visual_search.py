from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
import hashlib

from django.core.files.storage import default_storage
from django.db import transaction

from apps.ai.application.use_cases.log_ai_request import LogAIRequestCommand, LogAIRequestUseCase
from apps.ai.domain.policies import validate_image_upload
from apps.ai.domain.types import SearchResult
from apps.ai.infrastructure.embeddings.vector_store import search_similar, upsert_embedding
from apps.ai.infrastructure.embeddings.image_attributes import extract_from_bytes as extract_image_attributes
from apps.ai.infrastructure.providers.registry import get_provider
from apps.ai.models import AIProductEmbedding
from apps.catalog.models import Product
from apps.tenants.domain.tenant_context import TenantContext
from apps.analytics.application.telemetry import TelemetryService, actor_from_tenant_ctx


@dataclass(frozen=True)
class VisualSearchCommand:
    tenant_ctx: TenantContext
    image_file: object
    top_n: int = 12
    price_min: float | None = None
    price_max: float | None = None
    color: str | None = None
    brightness: str | None = None
    category: str | None = None
    material: str | None = None
    style: str | None = None
    white_background: bool | None = None


class VisualSearchUseCase:
    @staticmethod
    def execute(cmd: VisualSearchCommand) -> SearchResult:
        provider = get_provider()
        started = monotonic()
        warnings: list[str] = []
        try:
            validate_image_upload(cmd.image_file)
            image_bytes = cmd.image_file.read() if cmd.image_file else b''
            query_vector = provider.embed_image(image_bytes=image_bytes).vector
            query_attrs = extract_image_attributes(image_bytes) if image_bytes else {}
            _ensure_embeddings(cmd.tenant_ctx.tenant_id, provider_code=getattr(provider, "code", ""))
            raw_results = search_similar(store_id=cmd.tenant_ctx.tenant_id, vector=query_vector, top_n=max(cmd.top_n * 5, cmd.top_n))
            filtered = _apply_filters(
                raw_results,
                price_min=cmd.price_min,
                price_max=cmd.price_max,
                color=cmd.color,
                brightness=cmd.brightness,
                category=cmd.category,
                material=cmd.material,
                style=cmd.style,
                white_background=cmd.white_background,
                top_n=max(cmd.top_n * 3, cmd.top_n),
            )
            results = _rerank(filtered, query_attrs=query_attrs)[:cmd.top_n]
            data = [
                {
                    "product_id": item["product"].id,
                    "name": item["product"].name,
                    "score": round(item["score"], 4),
                    "price": float(item["product"].price),
                    "image": getattr(item["product"].image, "url", None),
                    "attributes": item.get("attributes") or {},
                }
                for item in results
            ]
            LogAIRequestUseCase.execute(
                LogAIRequestCommand(
                    store_id=cmd.tenant_ctx.tenant_id,
                    feature="SEARCH",
                    provider=getattr(provider, "code", ""),
                    latency_ms=int((monotonic() - started) * 1000),
                    token_count=None,
                    cost_estimate=0,
                    status="SUCCESS",
                )
            )
            TelemetryService.track(
                event_name="ai.visual_search_used",
                tenant_ctx=cmd.tenant_ctx,
                actor_ctx=actor_from_tenant_ctx(tenant_ctx=cmd.tenant_ctx, actor_type="MERCHANT"),
                properties={
                    "status": "success",
                    "result_count": len(data),
                    "provider_code": getattr(provider, "code", ""),
                },
            )
            return SearchResult(results=data, provider=getattr(provider, "code", ""), warnings=warnings, query_attributes=query_attrs)
        except Exception:
            LogAIRequestUseCase.execute(
                LogAIRequestCommand(
                    store_id=cmd.tenant_ctx.tenant_id,
                    feature="SEARCH",
                    provider=getattr(provider, "code", ""),
                    latency_ms=int((monotonic() - started) * 1000),
                    token_count=None,
                    cost_estimate=0,
                    status="FAILED",
                )
            )
            TelemetryService.track(
                event_name="ai.visual_search_used",
                tenant_ctx=cmd.tenant_ctx,
                actor_ctx=actor_from_tenant_ctx(tenant_ctx=cmd.tenant_ctx, actor_type="MERCHANT"),
                properties={
                    "status": "failed",
                    "result_count": 0,
                    "reason_code": "embedding_failed",
                    "provider_code": getattr(provider, "code", ""),
                },
            )
            return SearchResult(
                results=[],
                provider=getattr(provider, "code", ""),
                warnings=["fallback_used"],
                fallback_reason="embedding_failed",
            )


def _apply_filters(items: list[dict], *, price_min: float | None, price_max: float | None, color: str | None, brightness: str | None, category: str | None, material: str | None, style: str | None, white_background: bool | None, top_n: int) -> list[dict]:
    """Filter and trim search results for MVP."""
    out: list[dict] = []
    color_norm = (color or "").strip().lower() or None

    for item in items:
        product = item.get("product")
        if not product:
            continue

        price = float(getattr(product, "price", 0) or 0)
        if price_min is not None and price < float(price_min):
            continue
        if price_max is not None and price > float(price_max):
            continue

        if color_norm:
            attrs = (item.get("attributes") or {})
            dom = (attrs.get("dominant_color") or "").strip().lower()
            if dom != color_norm:
                continue

        # brightness filter
        if brightness:
            attrs = (item.get("attributes") or {})
            br = (attrs.get("brightness") or "").strip().lower()
            if br != brightness.strip().lower():
                continue

        # category/material/style filters (from CLIP guesses when enabled)
        if category:
            attrs = (item.get("attributes") or {})
            cg = (attrs.get("category_guess") or {})
            lbl = (cg.get("label") or "").strip().lower()
            if lbl != category.strip().lower():
                continue

        if material:
            attrs = (item.get("attributes") or {})
            mg = (attrs.get("material_guess") or {})
            lbl = (mg.get("label") or "").strip().lower()
            if lbl != material.strip().lower():
                continue

        if style:
            attrs = (item.get("attributes") or {})
            sg = (attrs.get("style_guess") or {})
            lbl = (sg.get("label") or "").strip().lower()
            if lbl != style.strip().lower():
                continue

        if white_background is not None:
            attrs = (item.get("attributes") or {})
            wb = bool(attrs.get("white_background"))
            if wb != bool(white_background):
                continue

        out.append(item)
        if len(out) >= top_n:
            break

    return out


def _rerank(items: list[dict], *, query_attrs: dict | None) -> list[dict]:
    """Light reranking using attribute matches.

    We combine base similarity score with small bonuses when extracted attributes match.
    This improves relevance for MVP without introducing a heavy reranker model.
    """
    qa = query_attrs or {}
    q_color = (qa.get("dominant_color") or "").strip().lower()
    q_brightness = (qa.get("brightness") or "").strip().lower()
    q_wb = qa.get("white_background", None)
    q_cat = ((qa.get("category_guess") or {}).get("label") or "").strip().lower()
    q_mat = ((qa.get("material_guess") or {}).get("label") or "").strip().lower()
    q_style = ((qa.get("style_guess") or {}).get("label") or "").strip().lower()

    def bonus(attrs: dict) -> float:
        b = 0.0
        if q_color and (attrs.get("dominant_color") or "").strip().lower() == q_color:
            b += 0.05
        if q_brightness and (attrs.get("brightness") or "").strip().lower() == q_brightness:
            b += 0.02
        if q_wb is not None and bool(attrs.get("white_background")) == bool(q_wb):
            b += 0.02
        if q_cat and ((attrs.get("category_guess") or {}).get("label") or "").strip().lower() == q_cat:
            b += 0.05
        if q_mat and ((attrs.get("material_guess") or {}).get("label") or "").strip().lower() == q_mat:
            b += 0.03
        if q_style and ((attrs.get("style_guess") or {}).get("label") or "").strip().lower() == q_style:
            b += 0.03
        return b

    out = []
    for item in items:
        attrs = item.get("attributes") or {}
        base_score = float(item.get("score") or 0.0)
        item["score"] = base_score + bonus(attrs)
        out.append(item)

    out.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    return out


@transaction.atomic
def _ensure_embeddings(store_id: int, provider_code: str, limit: int = 200) -> None:
    """Ensure we have embeddings for products in this store.

    - Computes image fingerprint (sha256) and only recomputes if changed.
    - Rebuilds FAISS index once after batch updates.
    """
    from apps.ai.infrastructure.embeddings.vector_store_faiss import is_available as faiss_available, build_index as faiss_build_index

    products = Product.objects.filter(store_id=store_id, image__isnull=False, is_active=True).order_by("-id")[:limit]
    changed = False
    for product in products:
        try:
            if not product.image:
                continue
            with default_storage.open(product.image.name, "rb") as handle:
                image_bytes = handle.read()
            fp = hashlib.sha256(image_bytes).hexdigest() if image_bytes else ""

            emb_obj = AIProductEmbedding.objects.filter(product_id=product.id).first()
            if emb_obj and emb_obj.vector and emb_obj.image_fingerprint and emb_obj.image_fingerprint == fp:
                continue

            provider = get_provider()
            vector = provider.embed_image(image_bytes=image_bytes).vector
            attrs = extract_image_attributes(image_bytes) if image_bytes else {}
            upsert_embedding(
                store_id=store_id,
                product_id=product.id,
                vector=vector,
                provider=provider_code,
                attributes=attrs,
                image_fingerprint=fp,
                rebuild_index=False,
            )
            changed = True
        except Exception:
            continue

    if changed and faiss_available():
        faiss_build_index(store_id=store_id)


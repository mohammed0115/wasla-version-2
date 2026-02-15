from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from django.db import transaction
from django.core.files.storage import default_storage
import hashlib

from ai.application.use_cases.log_ai_request import LogAIRequestCommand, LogAIRequestUseCase
from ai.infrastructure.embeddings.image_attributes import extract_from_bytes as extract_image_attributes
from ai.infrastructure.providers.registry import get_provider
from ai.infrastructure.embeddings.vector_store import upsert_embedding
from ai.models import AIProductEmbedding
from catalog.models import Product
from tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class IndexProductEmbeddingsCommand:
    tenant_ctx: TenantContext
    product_ids: list[int] | None = None
    force: bool = False


class IndexProductEmbeddingsUseCase:
    """Compute and store embeddings for products with images (store-scoped)."""

    @staticmethod
    @transaction.atomic
    def execute(cmd: IndexProductEmbeddingsCommand) -> dict:
        provider = get_provider()
        started = monotonic()

        qs = Product.objects.filter(store_id=cmd.tenant_ctx.tenant_id, is_active=True).exclude(image="")
        if cmd.product_ids:
            qs = qs.filter(id__in=cmd.product_ids)

        indexed = 0
        skipped = 0
        errors: list[str] = []

        for p in qs.iterator():
            try:
                if not p.image:
                    skipped += 1
                    continue

                # Read bytes from storage reliably
                with default_storage.open(p.image.name, "rb") as handle:
                    image_bytes = handle.read()

                fp = hashlib.sha256(image_bytes).hexdigest() if image_bytes else ""
                existing_fp = ""
                if hasattr(p, "ai_embedding") and p.ai_embedding:
                    existing_fp = getattr(p.ai_embedding, "image_fingerprint", "") or ""
                    if (not cmd.force) and existing_fp and existing_fp == fp and getattr(p.ai_embedding, "vector", None):
                        skipped += 1
                        continue

                emb = provider.embed_image(image_bytes=image_bytes)
                attrs = extract_image_attributes(image_bytes) if image_bytes else {}

                upsert_embedding(
                    store_id=cmd.tenant_ctx.tenant_id,
                    product_id=p.id,
                    vector=emb.vector,
                    provider=getattr(emb, "provider", ""),
                    attributes=attrs,
                    image_fingerprint=fp,
                    rebuild_index=False,
                )
                indexed += 1
            except Exception as e:
                errors.append(f"product_id={p.id}: {e}")
                continue

        latency_ms = int((monotonic() - started) * 1000)
        LogAIRequestUseCase.execute(
            LogAIRequestCommand(
                store_id=cmd.tenant_ctx.tenant_id,
                feature="SEARCH",
                provider=getattr(provider, "code", ""),
                latency_ms=latency_ms,
                token_count=None,
                cost_estimate=0,
                status="SUCCESS" if not errors else "FAILED",
            )
        )

        return {
            "indexed": indexed,
            "skipped": skipped,
            "errors": errors,
            "latency_ms": latency_ms,
        }

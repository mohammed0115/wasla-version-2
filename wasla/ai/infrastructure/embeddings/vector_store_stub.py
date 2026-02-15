from __future__ import annotations

import math

from django.db import transaction

from ai.models import AIProductEmbedding


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    length = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(length))
    norm_a = math.sqrt(sum(a[i] * a[i] for i in range(length)))
    norm_b = math.sqrt(sum(b[i] * b[i] for i in range(length)))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@transaction.atomic
def upsert_embedding(*, store_id: int, product_id: int, vector: list[float], provider: str):
    embedding, _ = AIProductEmbedding.objects.get_or_create(product_id=product_id, defaults={"store_id": store_id})
    embedding.store_id = store_id
    embedding.vector = vector
    embedding.provider = provider
    embedding.save(update_fields=["store_id", "vector", "provider", "updated_at"])
    return embedding


def search_similar(*, store_id: int, vector: list[float], top_n: int = 5) -> list[dict]:
    embeddings = AIProductEmbedding.objects.filter(store_id=store_id).select_related("product")
    scored = []
    for emb in embeddings:
        score = _cosine_similarity(vector, emb.vector or [])
        scored.append({"product": emb.product, "score": score})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_n]

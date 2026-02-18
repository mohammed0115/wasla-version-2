from __future__ import annotations

from django.db import transaction

from apps.ai.models import AIProductEmbedding

from .vector_store_stub import search_similar as _search_stub
from .vector_store_stub import upsert_embedding as _upsert_stub
from .vector_store_faiss import build_index, is_available, search as _faiss_search


@transaction.atomic
def upsert_embedding(*, store_id: int, product_id: int, vector: list[float], provider: str, attributes: dict | None = None, image_fingerprint: str | None = None, rebuild_index: bool = True):
    """
    Upsert embedding in DB, then rebuild FAISS index (store-scoped) when available.

    Rebuild strategy is simple and reliable for MVP:
    - For typical store sizes, rebuild is fast enough.
    - For large catalogs, we can switch to an IVF/HNSW index and incremental updates later.
    """
    embedding, _ = AIProductEmbedding.objects.get_or_create(product_id=product_id, defaults={"store_id": store_id})
    embedding.store_id = store_id
    embedding.vector = vector
    embedding.provider = provider
    if image_fingerprint is not None:
        embedding.image_fingerprint = image_fingerprint
    if attributes is not None:
        embedding.attributes = attributes
    embedding.save(update_fields=["store_id", "vector", "provider", "attributes", "image_fingerprint", "updated_at"])

    if rebuild_index and is_available():
        # Rebuild index after changes to keep search consistent.
        build_index(store_id=store_id)

    return embedding


def search_similar(*, store_id: int, vector: list[float], top_n: int = 5) -> list[dict]:
    """
    Returns list[{"product": Product, "score": float}] compatible with old stub.
    """
    if not is_available():
        return _search_stub(store_id=store_id, vector=vector, top_n=top_n)

    # query more to allow filtering later at caller level if needed
    pairs = _faiss_search(store_id=store_id, vector=vector, top_k=max(top_n, 10))
    if not pairs:
        return []

    # fetch products via embeddings (single query)
    qs = AIProductEmbedding.objects.filter(store_id=store_id, product_id__in=[pid for pid, _ in pairs]).select_related("product")
    by_pid = {e.product_id: e for e in qs}

    results: list[dict] = []
    for pid, score in pairs:
        emb = by_pid.get(pid)
        if not emb or not emb.product:
            continue
        results.append({"product": emb.product, "score": float(score), "attributes": emb.attributes or {}})

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_n]

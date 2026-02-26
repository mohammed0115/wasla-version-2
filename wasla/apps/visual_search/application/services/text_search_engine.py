from __future__ import annotations

from decimal import Decimal

from apps.visual_search.application.services.embedding_service import EmbeddingService
from apps.visual_search.infrastructure.repositories.django_visual_search_repository import (
    DjangoVisualSearchRepository,
)


class VisualTextSearchEngine:
    """Text query adapter over the existing visual-search ranking pipeline."""

    def __init__(self):
        self.embedding_service = EmbeddingService(embedding_dim=512)
        self.repository = DjangoVisualSearchRepository()

    def search(
        self,
        *,
        tenant_id: int,
        query_text: str,
        max_results: int = 12,
        min_price=None,
        max_price=None,
        sort_by: str = "similarity",
    ) -> list[dict]:
        normalized_query = (query_text or "").strip()
        if not normalized_query:
            return []

        embedding_vector = self.embedding_service.generate_embedding(normalized_query.encode("utf-8"), features={})

        found = self.repository.find_similar_products(
            tenant_id=tenant_id,
            embedding_vector=embedding_vector,
            limit=max_results,
            min_price=min_price,
            max_price=max_price,
            sort_by=sort_by,
        )

        results: list[dict] = []
        for item in found:
            price_value = item.extracted_attributes.get("price") or "0"
            if isinstance(price_value, Decimal):
                price_value = f"{price_value:.2f}"
            results.append(
                {
                    "product_id": item.product_id,
                    "title": str(item.extracted_attributes.get("title") or ""),
                    "price": str(price_value),
                    "currency": str(item.extracted_attributes.get("currency") or "SAR"),
                    "similarity": item.similarity_score.value,
                    "image_url": str(item.extracted_attributes.get("image_url") or ""),
                }
            )

        return results

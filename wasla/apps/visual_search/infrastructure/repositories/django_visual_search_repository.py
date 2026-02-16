from __future__ import annotations

from apps.visual_search.domain.entities import VisualSearchResult
from apps.visual_search.domain.value_objects import SimilarityScore
from apps.visual_search.infrastructure.models import ProductEmbedding


class DjangoVisualSearchRepository:
    def find_similar_products(
        self,
        *,
        tenant_id: int,
        embedding_vector: list[float],
        limit: int,
    ) -> list[VisualSearchResult]:
        hint_anchor = float(embedding_vector[0]) if embedding_vector else 0.0

        rows = (
            ProductEmbedding.objects.select_related("product")
            .only(
                "store_id",
                "similarity_hint",
                "product_id",
                "product__id",
                "product__store_id",
                "product__name",
                "product__price",
                "product__image",
                "product__is_active",
            )
            .filter(
                store_id=tenant_id,
                product__store_id=tenant_id,
                product__is_active=True,
            )
            .order_by("-similarity_hint", "-product_id")[:limit]
        )

        results: list[VisualSearchResult] = []
        for row in rows:
            raw_score = max(0.0, min(1.0, row.similarity_hint))
            adjusted_score = max(0.0, min(1.0, (raw_score + hint_anchor) / 2.0))
            image_url = row.product.image.url if row.product.image else ""
            results.append(
                VisualSearchResult(
                    product_id=row.product_id,
                    similarity_score=SimilarityScore(adjusted_score),
                    extracted_attributes={
                        "title": row.product.name,
                        "price": row.product.price,
                        "image_url": image_url,
                    },
                )
            )
        return results

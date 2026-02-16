from __future__ import annotations

from decimal import Decimal

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
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        sort_by: str = "similarity",
    ) -> list[VisualSearchResult]:
        hint_anchor = float(embedding_vector[0]) if embedding_vector else 0.0

        queryset = (
            ProductEmbedding.objects.select_related("product")
            .only(
                "store_id",
                "similarity_hint",
                "product_id",
                "created_at",
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
        )

        if min_price is not None:
            queryset = queryset.filter(product__price__gte=min_price)
        if max_price is not None:
            queryset = queryset.filter(product__price__lte=max_price)

        normalized_sort = (sort_by or "similarity").strip().lower()
        if normalized_sort == "price_low":
            queryset = queryset.order_by("product__price", "-similarity_hint", "-product_id")
        elif normalized_sort == "price_high":
            queryset = queryset.order_by("-product__price", "-similarity_hint", "-product_id")
        elif normalized_sort == "newest":
            product_model = ProductEmbedding._meta.get_field("product").related_model
            product_field_names = {field.name for field in product_model._meta.fields}
            if "created_at" in product_field_names:
                queryset = queryset.order_by("-product__created_at", "-product_id")
            else:
                queryset = queryset.order_by("-similarity_hint", "-product_id")
        else:
            queryset = queryset.order_by("-similarity_hint", "-product_id")

        rows = queryset[:limit]

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
                        "currency": "SAR",
                    },
                )
            )
        return results

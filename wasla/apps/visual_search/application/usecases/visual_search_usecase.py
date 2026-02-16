from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal

from apps.visual_search.application.dto.visual_search_dto import (
    VisualSearchQueryDTO,
    VisualSearchResultDTO,
)
from apps.visual_search.application.interfaces.repository_port import VisualSearchRepositoryPort
from apps.visual_search.domain.errors import InvalidImageError


@dataclass(frozen=True)
class VisualSearchUseCase:
    repository: VisualSearchRepositoryPort
    max_file_size_bytes: int = 5 * 1024 * 1024

    def execute(self, query: VisualSearchQueryDTO) -> list[VisualSearchResultDTO]:
        self._validate_query(query)

        embedding_vector, _attributes = self._extract_features(query)
        found = self.repository.find_similar_products(
            tenant_id=query.tenant_id,
            embedding_vector=embedding_vector,
            limit=query.max_results,
        )
        if not found:
            return self._safe_fallback()

        mapped: list[VisualSearchResultDTO] = []
        for row in found:
            attr_title = str(row.extracted_attributes.get("title") or "")
            attr_image_url = str(row.extracted_attributes.get("image_url") or "")
            price_raw = row.extracted_attributes.get("price") or "0"
            mapped.append(
                VisualSearchResultDTO(
                    product_id=row.product_id,
                    title=attr_title,
                    price=Decimal(str(price_raw)),
                    similarity_score=row.similarity_score.value,
                    image_url=attr_image_url,
                )
            )

        results = self._apply_filters_and_sort(mapped, query)

        if not results:
            return self._safe_fallback()
        return results

    def _safe_fallback(self) -> list[VisualSearchResultDTO]:
        return []

    def _validate_query(self, query: VisualSearchQueryDTO) -> None:
        if query.tenant_id <= 0:
            raise InvalidImageError("Invalid tenant id.")
        has_file = query.image_file is not None
        has_url = bool((query.image_url or "").strip())
        if not has_file and not has_url:
            raise InvalidImageError("Image file or image URL is required.")
        if query.max_results < 1:
            raise InvalidImageError("max_results must be at least 1.")

        if has_file:
            image_file = query.image_file
            file_name = str(getattr(image_file, "name", "")).lower()
            content_type = str(getattr(image_file, "content_type", "")).lower()
            size = int(getattr(image_file, "size", 0) or 0)
            allowed_extensions = (".jpg", ".jpeg", ".png", ".webp")
            if not file_name.endswith(allowed_extensions):
                raise InvalidImageError("Unsupported file extension.")
            if content_type and content_type not in {
                "image/jpeg",
                "image/jpg",
                "image/png",
                "image/webp",
            }:
                raise InvalidImageError("Unsupported image MIME type.")
            if size <= 0 or size > self.max_file_size_bytes:
                raise InvalidImageError("Invalid image file size.")

    def _extract_features(self, query: VisualSearchQueryDTO) -> tuple[list[float], dict]:
        if query.image_file is not None:
            payload = f"file:{getattr(query.image_file, 'name', '')}:{getattr(query.image_file, 'size', 0)}"
        else:
            payload = f"url:{(query.image_url or '').strip()}"

        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        vector = [round(byte / 255.0, 6) for byte in digest[:16]]
        attributes = {
            "source": "mock-visual-ai",
            "has_file": query.image_file is not None,
            "has_url": bool(query.image_url),
        }
        return vector, attributes

    def _apply_filters_and_sort(
        self,
        results: list[VisualSearchResultDTO],
        query: VisualSearchQueryDTO,
    ) -> list[VisualSearchResultDTO]:
        filtered = list(results)

        if query.min_price:
            try:
                min_value = Decimal(str(query.min_price))
                filtered = [row for row in filtered if row.price >= min_value]
            except Exception:
                pass

        if query.max_price:
            try:
                max_value = Decimal(str(query.max_price))
                filtered = [row for row in filtered if row.price <= max_value]
            except Exception:
                pass

        if query.sort_by == "price_asc":
            filtered.sort(key=lambda row: row.price)
        elif query.sort_by == "price_desc":
            filtered.sort(key=lambda row: row.price, reverse=True)
        else:
            filtered.sort(key=lambda row: row.similarity_score, reverse=True)

        return filtered

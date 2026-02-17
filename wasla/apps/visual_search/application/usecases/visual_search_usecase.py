from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO

from apps.visual_search.application.dto.visual_search_dto import (
    VisualSearchQueryDTO,
    VisualSearchResponseDTO,
    VisualSearchResultDTO,
)
from apps.visual_search.application.interfaces.repository_port import VisualSearchRepositoryPort
from apps.visual_search.application.services.image_processor import ImageProcessor
from apps.visual_search.application.services.embedding_service import EmbeddingService
from apps.visual_search.domain.errors import InvalidImageError


@dataclass(frozen=True)
class VisualSearchUseCase:
    repository: VisualSearchRepositoryPort
    max_file_size_bytes: int = 5 * 1024 * 1024

    def execute(self, query: VisualSearchQueryDTO) -> list[VisualSearchResultDTO]:
        return self.run(query).results

    def run(self, query: VisualSearchQueryDTO) -> VisualSearchResponseDTO:
        self._validate_query(query)

        embedding_vector, attributes = self._extract_features(query)
        found = self.repository.find_similar_products(
            tenant_id=query.tenant_id,
            embedding_vector=embedding_vector,
            limit=query.max_results,
            min_price=query.min_price,
            max_price=query.max_price,
            sort_by=query.sort_by,
        )
        if not found:
            return VisualSearchResponseDTO(results=self._safe_fallback(), attributes=attributes)

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
                    currency=str(row.extracted_attributes.get("currency") or "SAR"),
                )
            )
        return VisualSearchResponseDTO(results=mapped, attributes=attributes)

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
        """Extract features and embedding from image."""
        processor = ImageProcessor()
        embedding_service = EmbeddingService(embedding_dim=512)

        # Process image
        if query.image_file is not None:
            try:
                features = processor.process_image_file(query.image_file)
                # Generate embedding from image file
                query.image_file.seek(0)  # Reset file pointer
                embedding = embedding_service.generate_embedding(
                    query.image_file,
                    features.attributes
                )
            except Exception as exc:
                raise InvalidImageError(f"Failed to process image: {exc}")
        elif query.image_url:
            try:
                import requests
                response = requests.get(query.image_url, timeout=10)
                response.raise_for_status()
                features = processor.process_image_file(BytesIO(response.content))
                embedding = embedding_service.generate_embedding(response.content, features.attributes)
            except Exception as exc:
                raise InvalidImageError(f"Failed to fetch image from URL: {exc}")
        else:
            raise InvalidImageError("No image provided")

        attributes = {
            "source": "visual-ai",
            "colors": features.colors.color_names,
            "brightness": features.attributes.get("brightness", "medium"),
            "aspect_ratio": features.aspect_ratio,
            "has_pattern": features.attributes.get("has_pattern", False),
            "category_hint": features.attributes.get("category_hint", "general"),
        }

        return embedding, attributes

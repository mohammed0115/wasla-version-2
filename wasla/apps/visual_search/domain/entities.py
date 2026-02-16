from __future__ import annotations

from dataclasses import dataclass

from apps.visual_search.domain.value_objects import SimilarityScore


@dataclass(frozen=True)
class VisualSearchResult:
    product_id: int
    similarity_score: SimilarityScore
    extracted_attributes: dict

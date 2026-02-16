from __future__ import annotations

from typing import Protocol

from apps.visual_search.domain.entities import VisualSearchResult


class VisualSearchRepositoryPort(Protocol):
    def find_similar_products(
        self,
        *,
        tenant_id: int,
        embedding_vector: list[float],
        limit: int,
    ) -> list[VisualSearchResult]:
        raise NotImplementedError

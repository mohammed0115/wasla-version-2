from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from apps.visual_search.domain.entities import VisualSearchResult


class VisualSearchRepositoryPort(Protocol):
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
        raise NotImplementedError

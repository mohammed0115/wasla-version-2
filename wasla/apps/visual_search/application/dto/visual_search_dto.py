from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class VisualSearchQueryDTO:
    tenant_id: int
    image_file: object | None = None
    image_url: str | None = None
    max_results: int = 12
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    sort_by: str = "similarity"


@dataclass(frozen=True)
class VisualSearchResultDTO:
    product_id: int
    title: str
    price: Decimal
    similarity_score: float
    image_url: str
    currency: str = "SAR"


@dataclass(frozen=True)
class VisualSearchResponseDTO:
    results: list[VisualSearchResultDTO]
    attributes: dict

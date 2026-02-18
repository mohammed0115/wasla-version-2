from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class TextResult:
    text: str
    provider: str
    token_count: int | None = None


@dataclass(frozen=True)
class ClassificationResult:
    label: str
    confidence: float
    provider: str


@dataclass(frozen=True)
class VectorEmbedding:
    vector: list[float]
    provider: str


@dataclass(frozen=True)
class DescriptionResult:
    description: str
    language: str
    provider: str
    token_count: int | None
    warnings: list[str]
    fallback_reason: str | None = None


@dataclass(frozen=True)
class CategoryResult:
    category_id: int | None
    category_name: str | None
    confidence: float
    provider: str
    warnings: list[str]
    fallback_reason: str | None = None


@dataclass(frozen=True)
class SearchResult:
    results: Sequence[dict]
    provider: str
    warnings: list[str]
    query_attributes: dict | None = None
    fallback_reason: str | None = None

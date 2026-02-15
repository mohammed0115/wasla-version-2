from __future__ import annotations

from typing import Protocol

from .types import ClassificationResult, TextResult, VectorEmbedding


class AIProviderPort(Protocol):
    def generate_text(self, *, prompt: str, language: str, max_tokens: int) -> TextResult:
        ...

    def classify_text(self, *, text: str, labels: list[str]) -> ClassificationResult:
        ...

    def embed_image(self, *, image_bytes: bytes) -> VectorEmbedding:
        ...

from __future__ import annotations

import hashlib

from apps.ai.domain.types import ClassificationResult, TextResult, VectorEmbedding
from apps.ai.infrastructure.embeddings.image_embedder import image_embedding


class GoogleProvider:
    code = "google"

    def generate_text(self, *, prompt: str, language: str, max_tokens: int) -> TextResult:
        # Stubbed provider for Phase 4 (replace with Vertex AI later).
        text = prompt.split("\\n")[-1][:max_tokens]
        return TextResult(text=text, provider=self.code, token_count=None)

    def classify_text(self, *, text: str, labels: list[str]) -> ClassificationResult:
        label = labels[0] if labels else ""
        return ClassificationResult(label=label, confidence=0.4, provider=self.code)

    def embed_image(self, *, image_bytes: bytes) -> VectorEmbedding:
        vector = image_embedding(image_bytes)
        return VectorEmbedding(vector=vector, provider=self.code)

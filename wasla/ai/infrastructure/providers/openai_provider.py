from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import requests
from django.conf import settings

from ai.domain.types import ClassificationResult, TextResult, VectorEmbedding
from ai.infrastructure.embeddings.image_embedder import image_embedding


class OpenAIProvider:
    code = "openai"

    def __init__(self):
        self.api_key = getattr(settings, "OPENAI_API_KEY", "") or ""
        self.model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
        self.timeout = int(getattr(settings, "AI_TIMEOUT_SECONDS", 15))

    def generate_text(self, *, prompt: str, language: str, max_tokens: int) -> TextResult:
        if not self.api_key:
            raise ValueError("OpenAI API key not configured.")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant for e-commerce merchants."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise ValueError("OpenAI request failed.")
        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
        tokens = data.get("usage", {}).get("total_tokens")
        return TextResult(text=text.strip(), provider=self.code, token_count=tokens)

    def classify_text(self, *, text: str, labels: list[str]) -> ClassificationResult:
        if not labels:
            return ClassificationResult(label="", confidence=0.0, provider=self.code)
        prompt = (
            "Choose the best label from this list and return ONLY the label:\n"
            f"Labels: {', '.join(labels)}\n"
            f"Text: {text}"
        )
        result = self.generate_text(prompt=prompt, language="en", max_tokens=50)
        label = (result.text or "").strip()
        if label not in labels:
            label = labels[0]
        return ClassificationResult(label=label, confidence=0.6, provider=self.code)

    def embed_image(self, *, image_bytes: bytes) -> VectorEmbedding:
        vector = image_embedding(image_bytes)
        return VectorEmbedding(vector=vector, provider=self.code)

from __future__ import annotations

import hashlib
from typing import Any
import struct

try:
    import numpy as np
except ImportError:
    np = None


class EmbeddingService:
    """Generates embedding vectors from images."""

    def __init__(self, embedding_dim: int = 512):
        self.embedding_dim = embedding_dim

    def generate_embedding(self, image_data: bytes | Any, features: dict | None = None) -> list[float]:
        """
        Generate embedding vector from image data.
        
        This is a placeholder implementation using spatial hashing.
        In production, this would use a real model like CLIP, ResNet, or similar.
        
        Args:
            image_data: Image bytes or file-like object
            features: Optional extracted image features
            
        Returns:
            List of floats representing the embedding vector
        """
        # Create stable hash from image data
        if hasattr(image_data, "read"):
            data_bytes = image_data.read()
        else:
            data_bytes = image_data if isinstance(image_data, bytes) else str(image_data).encode()

        # Use SHA256 to get consistent hash
        hash_obj = hashlib.sha256(data_bytes)
        hash_bytes = hash_obj.digest()  # 32 bytes

        # Convert to embedding using deterministic method
        embedding = self._hash_to_embedding(hash_bytes, self.embedding_dim)

        # Optionally augment with feature information
        if features:
            embedding = self._augment_with_features(embedding, features)

        return embedding

    def _hash_to_embedding(self, hash_bytes: bytes, dim: int) -> list[float]:
        """
        Convert hash bytes to embedding vector.
        
        Uses simple deterministic expansion of hash to create
        a continuous vector space representation.
        """
        if np is None:
            # Fallback without numpy
            embedding = []
            for i in range(dim):
                byte_idx = (i * len(hash_bytes)) // dim
                byte_val = hash_bytes[byte_idx]
                embedding.append((byte_val / 127.5) - 1.0)
            return embedding

        # Use numpy for efficiency
        # Repeat hash bytes to fill embedding dimension
        repeated = np.tile(hash_bytes, (dim // len(hash_bytes)) + 1)[:dim]
        # Normalize to [-1, 1] range
        embedding = (repeated.astype(np.float32) / 127.5) - 1.0
        return embedding.tolist()

    def _augment_with_features(self, embedding: list[float], features: dict) -> list[float]:
        """
        Augment embedding with extracted features.
        
        This helps encode color and attribute information into the vector.
        """
        if not np:
            return embedding

        embedding = np.array(embedding, dtype=np.float32)

        # Encode color information if available
        colors = features.get("color_names", [])
        if colors:
            # Create one-hot-like encoding for colors
            color_hash = hashlib.md5(str(colors).encode()).digest()
            color_vector = np.array([b / 127.5 - 1.0 for b in color_hash])
            # Mix color info into embedding (first 16 dimensions)
            embedding[:min(16, len(color_vector))] = (
                embedding[:min(16, len(color_vector))] * 0.7 + color_vector[:len(embedding)] * 0.3
            )

        # Encode brightness
        brightness = features.get("brightness", "medium")
        brightness_codes = {"dark": -0.5, "medium": 0.0, "bright": 0.5}
        brightness_value = brightness_codes.get(brightness, 0.0)
        embedding[(-4)] += brightness_value * 0.2

        # Encode pattern detection
        has_pattern = features.get("has_pattern", False)
        embedding[(-3)] += (0.5 if has_pattern else -0.5) * 0.2

        # L2 normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding.tolist()

    def similarity(self, embedding1: list[float], embedding2: list[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Returns value between -1 (opposite) and 1 (identical).
        For similarity scoring, we typically use (similarity + 1) / 2 to get [0, 1].
        """
        if not embedding1 or not embedding2:
            return 0.0

        if np is None:
            # Fallback without numpy
            dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
            norm1 = (sum(a**2 for a in embedding1)) ** 0.5
            norm2 = (sum(b**2 for b in embedding2)) ** 0.5
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return dot_product / (norm1 * norm2)

        v1 = np.array(embedding1, dtype=np.float32)
        v2 = np.array(embedding2, dtype=np.float32)
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8))

    def normalize_score(self, similarity: float) -> float:
        """
        Convert similarity score from [-1, 1] range to [0, 1] percentage.
        """
        # Clamp to [-1, 1]
        similarity = max(-1.0, min(1.0, similarity))
        # Convert to [0, 1]
        return (similarity + 1.0) / 2.0

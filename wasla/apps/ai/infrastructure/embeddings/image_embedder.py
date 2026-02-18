from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from django.conf import settings

from apps.ai.domain.types import VectorEmbedding

# Fallback handcrafted embedding (always available)
from apps.ai.infrastructure.embeddings.image_features import image_embedding as _fallback_image_embedding

try:
    # Optional heavy deps
    import torch  # type: ignore
    from transformers import CLIPModel, CLIPProcessor  # type: ignore
except Exception:  # pragma: no cover
    torch = None  # type: ignore
    CLIPModel = None  # type: ignore
    CLIPProcessor = None  # type: ignore


@dataclass
class ImageEmbeddingResult:
    vector: VectorEmbedding
    provider: str
    dim: int


_CLIP_CACHE: dict[str, tuple[object, object]] = {}


def _clip_is_available() -> bool:
    return torch is not None and CLIPModel is not None and CLIPProcessor is not None


def _get_clip(model_name: str) -> Tuple[object, object]:
    if model_name in _CLIP_CACHE:
        return _CLIP_CACHE[model_name]
    model = CLIPModel.from_pretrained(model_name)
    processor = CLIPProcessor.from_pretrained(model_name)
    model.eval()
    _CLIP_CACHE[model_name] = (model, processor)
    return model, processor


def image_embedding(image_bytes: bytes) -> ImageEmbeddingResult:
    """
    Returns an embedding for an input image.

    Priority:
    1) CLIP (if torch+transformers installed and CLIP enabled)
    2) Lightweight handcrafted embedding (always available)

    Notes:
    - CLIP output is L2-normalized.
    - Fallback embedding is already normalized in image_features.
    """
    use_clip = bool(getattr(settings, "AI_USE_CLIP_EMBEDDINGS", False))
    model_name = getattr(settings, "AI_CLIP_MODEL_NAME", "openai/clip-vit-base-patch32")

    if use_clip and _clip_is_available():
        model, processor = _get_clip(model_name)

        # Load image via PIL to keep compatibility across transformers versions.
        try:
            from PIL import Image  # type: ignore
            import io
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            inputs = processor(images=img, return_tensors="pt")
        except Exception:
            # If PIL/bytes fail for any reason, fall back safely.
            inputs = None

        if inputs is not None:
            with torch.no_grad():
                feats = model.get_image_features(**inputs)
                feats = feats / feats.norm(dim=-1, keepdim=True).clamp(min=1e-12)
            vec = feats[0].cpu().numpy().astype("float32").tolist()
            return ImageEmbeddingResult(vector=vec, provider="clip", dim=len(vec))

    vec = _fallback_image_embedding(image_bytes)
    return ImageEmbeddingResult(vector=vec, provider="handcrafted", dim=len(vec))

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

from django.conf import settings

try:
    import torch  # type: ignore
    from transformers import CLIPModel, CLIPProcessor  # type: ignore
except Exception:  # pragma: no cover
    torch = None  # type: ignore
    CLIPModel = None  # type: ignore
    CLIPProcessor = None  # type: ignore


@dataclass
class ClipClassification:
    label: str
    score: float


_CLIP_TEXT_CACHE: dict[str, dict[str, Any]] = {}


def is_available() -> bool:
    return torch is not None and CLIPModel is not None and CLIPProcessor is not None


def _get_model(model_name: str):
    if model_name in _CLIP_TEXT_CACHE and "model" in _CLIP_TEXT_CACHE[model_name]:
        cache = _CLIP_TEXT_CACHE[model_name]
        return cache["model"], cache["processor"]
    model = CLIPModel.from_pretrained(model_name)
    processor = CLIPProcessor.from_pretrained(model_name)
    model.eval()
    _CLIP_TEXT_CACHE.setdefault(model_name, {})
    _CLIP_TEXT_CACHE[model_name]["model"] = model
    _CLIP_TEXT_CACHE[model_name]["processor"] = processor
    return model, processor


def _get_text_features(model_name: str, prompts: list[str]):
    cache = _CLIP_TEXT_CACHE.setdefault(model_name, {})
    key = "|".join(prompts)
    if key in cache:
        return cache[key]
    model, processor = _get_model(model_name)
    inputs = processor(text=prompts, return_tensors="pt", padding=True)
    with torch.no_grad():
        feats = model.get_text_features(**inputs)
        feats = feats / feats.norm(dim=-1, keepdim=True).clamp(min=1e-12)
    cache[key] = feats
    return feats


def classify_image(image_bytes: bytes, labels: list[str]) -> Optional[ClipClassification]:
    """
    Zero-shot style classification using CLIP similarity between image embedding and label prompts.
    Returns best label + score (cosine similarity).
    """
    if not is_available():
        return None
    if not labels:
        return None

    model_name = getattr(settings, "AI_CLIP_MODEL_NAME", "openai/clip-vit-base-patch32")
    model, processor = _get_model(model_name)

    # Make prompts more descriptive for better CLIP performance
    prompts = [f"a photo of {lbl}" for lbl in labels]
    text_feats = _get_text_features(model_name, prompts)

    try:
        from PIL import Image  # type: ignore
        import io
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = processor(images=img, return_tensors="pt")
    except Exception:
        return None

    with torch.no_grad():
        img_feats = model.get_image_features(**inputs)
        img_feats = img_feats / img_feats.norm(dim=-1, keepdim=True).clamp(min=1e-12)

    # cosine similarity
    sims = (img_feats @ text_feats.T)[0]
    best_idx = int(torch.argmax(sims).item())
    best_score = float(sims[best_idx].item())
    return ClipClassification(label=labels[best_idx], score=best_score)

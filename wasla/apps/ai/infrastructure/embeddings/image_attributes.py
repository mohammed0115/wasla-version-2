from __future__ import annotations

from typing import Any

import io

import numpy as np

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore

from django.conf import settings

from apps.ai.infrastructure.embeddings.clip_attributes import classify_image, is_available as clip_available


COLOR_BINS = [
    ("red", 0, 15),
    ("orange", 15, 35),
    ("yellow", 35, 60),
    ("green", 60, 150),
    ("cyan", 150, 200),
    ("blue", 200, 255),
]


def _dominant_hue_label(hue: float) -> str:
    for name, lo, hi in COLOR_BINS:
        if lo <= hue < hi:
            return name
    return "unknown"


def extract_from_bytes(image_bytes: bytes) -> dict[str, Any]:
    """
    Lightweight attribute extraction used for:
    - filtering (color/brightness)
    - UI hints (aspect)
    - optional CLIP-based category guess (if enabled)

    Returns:
      dominant_color: str
      brightness: dark|normal|bright
      saturation: low|normal|high
      aspect: portrait|square|landscape
      white_background: bool
      category_guess: {label, score} (optional)
    """
    base: dict[str, Any] = {
        "dominant_color": "unknown",
        "brightness": "unknown",
        "saturation": "unknown",
        "aspect": "unknown",
        "white_background": False,
    }

    if Image is None:
        return base

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    aspect = w / max(h, 1)
    if aspect > 1.2:
        base["aspect"] = "landscape"
    elif aspect < 0.8:
        base["aspect"] = "portrait"
    else:
        base["aspect"] = "square"

    # Downscale for speed
    arr = np.asarray(img.resize((128, 128))).astype("float32") / 255.0

    # brightness
    lum = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
    mean_lum = float(lum.mean())
    if mean_lum < 0.35:
        base["brightness"] = "dark"
    elif mean_lum > 0.70:
        base["brightness"] = "bright"
    else:
        base["brightness"] = "normal"

    # approximate saturation via max-min per pixel
    sat = (arr.max(axis=2) - arr.min(axis=2))
    mean_sat = float(sat.mean())
    if mean_sat < 0.10:
        base["saturation"] = "low"
    elif mean_sat > 0.30:
        base["saturation"] = "high"
    else:
        base["saturation"] = "normal"

    # background heuristic: corner pixels close to white
    corners = np.stack(
        [
            arr[0, 0],
            arr[0, -1],
            arr[-1, 0],
            arr[-1, -1],
        ],
        axis=0,
    )
    base["white_background"] = bool((corners.mean(axis=0) > 0.90).all())

    # dominant hue (rough): convert to HSV-ish by using max channel index;
    # we keep previous simplistic approach: compute hue proxy from RGB weighted.
    # A quick proxy: use OpenCV-like formula would be better, but keep deps light.
    # We'll approximate hue by channel dominance.
    r = arr[:, :, 0].flatten()
    g = arr[:, :, 1].flatten()
    b = arr[:, :, 2].flatten()
    # Hue proxy: map RGB to a 0..255 circle
    hue_proxy = (np.arctan2(np.sqrt(3) * (g - b), 2 * r - g - b) + np.pi) / (2 * np.pi)
    hue_val = float(np.median(hue_proxy) * 255.0)
    base["dominant_color"] = _dominant_hue_label(hue_val)

    # Optional CLIP category guess
    if bool(getattr(settings, "AI_USE_CLIP_CATEGORIES", False)) and clip_available():
        labels = list(getattr(settings, "AI_CLIP_CATEGORY_LABELS", [])) or [
            "shoes",
            "t-shirt",
            "dress",
            "bag",
            "watch",
            "pants",
            "jacket",
            "hoodie",
            "hat",
            "perfume",
            "sunglasses",
        ]
        res = classify_image(image_bytes, labels)
        if res:
            base["category_guess"] = {"label": res.label, "score": round(res.score, 4)}

    # Optional CLIP material guess
    if bool(getattr(settings, "AI_USE_CLIP_MATERIALS", False)) and clip_available():
        labels = list(getattr(settings, "AI_CLIP_MATERIAL_LABELS", [])) or [
            "leather",
            "cotton",
            "denim",
            "silk",
            "wool",
            "polyester",
            "linen",
            "metal",
            "plastic",
            "glass",
        ]
        res = classify_image(image_bytes, labels)
        if res:
            base["material_guess"] = {"label": res.label, "score": round(res.score, 4)}

    # Optional CLIP style guess
    if bool(getattr(settings, "AI_USE_CLIP_STYLES", False)) and clip_available():
        labels = list(getattr(settings, "AI_CLIP_STYLE_LABELS", [])) or [
            "casual",
            "formal",
            "sport",
            "streetwear",
            "classic",
            "minimal",
            "luxury",
            "vintage",
        ]
        # More helpful prompts for styles (still using classify_image helper)
        res = classify_image(image_bytes, labels)
        if res:
            base["style_guess"] = {"label": res.label, "score": round(res.score, 4)}

    return base

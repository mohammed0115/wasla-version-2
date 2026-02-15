from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import List

import numpy as np
from PIL import Image
from scipy.fftpack import dct
from scipy import ndimage


def _phash_bits(img: Image.Image, hash_size: int = 8, highfreq_factor: int = 4) -> np.ndarray:
    """Perceptual hash (pHash) bits using DCT.
    Returns (hash_size*hash_size,) array of 0/1 floats.
    """
    # Resize to (hash_size*highfreq_factor)
    size = hash_size * highfreq_factor
    gray = img.convert("L").resize((size, size), Image.BICUBIC)
    pixels = np.asarray(gray, dtype=np.float32)

    # 2D DCT
    dct_rows = dct(pixels, axis=0, norm="ortho")
    dct_2d = dct(dct_rows, axis=1, norm="ortho")

    # Top-left low frequencies
    low = dct_2d[:hash_size, :hash_size]
    # median excluding DC term
    med = np.median(low.flatten()[1:])
    bits = (low > med).astype(np.float32).flatten()
    return bits


def _hsv_hist(img: Image.Image, bins: int = 16) -> np.ndarray:
    hsv = img.convert("RGB").convert("HSV")
    arr = np.asarray(hsv, dtype=np.uint8)
    # H,S,V in [0,255]
    h = arr[..., 0]
    s = arr[..., 1]
    v = arr[..., 2]
    hist_h, _ = np.histogram(h, bins=bins, range=(0, 256), density=False)
    hist_s, _ = np.histogram(s, bins=bins, range=(0, 256), density=False)
    hist_v, _ = np.histogram(v, bins=bins, range=(0, 256), density=False)
    hist = np.concatenate([hist_h, hist_s, hist_v]).astype(np.float32)
    total = float(hist.sum()) or 1.0
    return hist / total


def _edge_hist(img: Image.Image, bins: int = 16) -> np.ndarray:
    gray = img.convert("L").resize((128, 128), Image.BICUBIC)
    arr = np.asarray(gray, dtype=np.float32) / 255.0
    sx = ndimage.sobel(arr, axis=0, mode="reflect")
    sy = ndimage.sobel(arr, axis=1, mode="reflect")
    mag = np.sqrt(sx * sx + sy * sy)
    hist, _ = np.histogram(mag, bins=bins, range=(0.0, float(mag.max() or 1.0)), density=False)
    hist = hist.astype(np.float32)
    total = float(hist.sum()) or 1.0
    return hist / total


def image_embedding(image_bytes: bytes) -> List[float]:
    """A lightweight, offline-safe image embedding.
    Not a deep model, but significantly better than sha/md5 stubs for similarity search.
    Output dim: 64 (pHash) + 48 (HSV hist) + 16 (edge hist) = 128
    """
    img = Image.open(BytesIO(image_bytes))
    # Normalize size for consistent features
    img_small = img.resize((256, 256), Image.BICUBIC)

    ph = _phash_bits(img_small, hash_size=8, highfreq_factor=4)  # 64
    hsv = _hsv_hist(img_small, bins=16)  # 48
    edge = _edge_hist(img_small, bins=16)  # 16

    vec = np.concatenate([ph, hsv, edge]).astype(np.float32)

    # L2 normalize
    norm = float(np.linalg.norm(vec)) or 1.0
    vec = vec / norm
    return vec.tolist()

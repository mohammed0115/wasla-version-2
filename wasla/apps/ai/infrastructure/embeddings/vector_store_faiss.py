from __future__ import annotations

import json
import os
from dataclasses import dataclass
from math import sqrt
from typing import Optional

import numpy as np
from django.conf import settings

from apps.ai.models import AIProductEmbedding

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None  # type: ignore


@dataclass
class FaissIndexBundle:
    index: object
    ids: list[int]
    dim: int


_CACHE: dict[int, FaissIndexBundle] = {}


def _index_dir(store_id: int) -> str:
    base = getattr(settings, "MEDIA_ROOT", None) or os.path.join(settings.BASE_DIR, "media")
    return os.path.join(base, "ai_indexes", f"store_{store_id}")


def _index_paths(store_id: int) -> tuple[str, str]:
    d = _index_dir(store_id)
    return os.path.join(d, "index.faiss"), os.path.join(d, "ids.json")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def is_available() -> bool:
    return faiss is not None


def _normalize(v: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return v / norms


def _make_index(dim: int, n: int) -> object:
    """Create FAISS index according to settings."""
    if faiss is None:
        raise RuntimeError("faiss not available")

    index_type = getattr(settings, "AI_FAISS_INDEX_TYPE", "flat").lower()  # flat|ivf
    if index_type == "ivf" and n >= 200:
        # Cosine sim via inner product on normalized vectors
        nlist = int(getattr(settings, "AI_FAISS_NLIST", 0) or max(32, min(4096, int(sqrt(n)) * 8)))
        quantizer = faiss.IndexFlatIP(dim)
        index = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT)
        return index

    return faiss.IndexFlatIP(dim)


def build_index(*, store_id: int) -> Optional[FaissIndexBundle]:
    """
    Build (or rebuild) a FAISS index from DB embeddings for a store.

    Notes:
    - Uses cosine similarity via inner-product on L2-normalized vectors.
    - Rebuild is reliable; for large catalogs use IVF for speed.
    """
    if faiss is None:
        return None

    qs = AIProductEmbedding.objects.filter(store_id=store_id).values_list("product_id", "vector")
    rows = list(qs)
    if not rows:
        bundle = FaissIndexBundle(index=faiss.IndexFlatIP(1), ids=[], dim=1)
        _CACHE[store_id] = bundle
        return bundle

    ids: list[int] = []
    vecs: list[list[float]] = []
    for pid, v in rows:
        if not v:
            continue
        ids.append(int(pid))
        vecs.append(list(v))

    if not vecs:
        bundle = FaissIndexBundle(index=faiss.IndexFlatIP(1), ids=[], dim=1)
        _CACHE[store_id] = bundle
        return bundle

    x = np.array(vecs, dtype="float32")
    dim = int(x.shape[1])
    x = _normalize(x)

    index = _make_index(dim, n=len(ids))

    # Train IVF index if needed
    if hasattr(index, "is_trained") and not index.is_trained:
        index.train(x)

    index.add(x)

    # search tuning
    nprobe = int(getattr(settings, "AI_FAISS_NPROBE", 0) or 16)
    if hasattr(index, "nprobe"):
        try:
            index.nprobe = nprobe
        except Exception:
            pass

    bundle = FaissIndexBundle(index=index, ids=ids, dim=dim)
    _CACHE[store_id] = bundle

    idx_file, ids_file = _index_paths(store_id)
    _ensure_dir(os.path.dirname(idx_file))
    faiss.write_index(index, idx_file)
    with open(ids_file, "w", encoding="utf-8") as f:
        json.dump({"ids": ids, "dim": dim}, f)

    return bundle


def load_index(*, store_id: int) -> Optional[FaissIndexBundle]:
    if faiss is None:
        return None
    if store_id in _CACHE:
        return _CACHE[store_id]

    idx_file, ids_file = _index_paths(store_id)
    if not os.path.exists(idx_file) or not os.path.exists(ids_file):
        return build_index(store_id=store_id)

    index = faiss.read_index(idx_file)
    with open(ids_file, "r", encoding="utf-8") as f:
        meta = json.load(f)
    ids = [int(x) for x in meta.get("ids", [])]
    dim = int(meta.get("dim", 1))

    # search tuning
    nprobe = int(getattr(settings, "AI_FAISS_NPROBE", 0) or 16)
    if hasattr(index, "nprobe"):
        try:
            index.nprobe = nprobe
        except Exception:
            pass

    bundle = FaissIndexBundle(index=index, ids=ids, dim=dim)
    _CACHE[store_id] = bundle
    return bundle


def search(*, store_id: int, vector: list[float], top_n: int = 5) -> list[dict]:
    """Return candidates list[{'product_id': int, 'score': float}]"""
    if faiss is None:
        return []
    bundle = load_index(store_id=store_id)
    if not bundle or not bundle.ids:
        return []

    q = np.array([vector], dtype="float32")
    q = _normalize(q)

    scores, idxs = bundle.index.search(q, top_n)
    res: list[dict] = []
    for j, score in zip(idxs[0], scores[0]):
        if j < 0:
            continue
        try:
            pid = bundle.ids[int(j)]
        except Exception:
            continue
        res.append({"product_id": int(pid), "score": float(score)})
    return res

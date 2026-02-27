from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any

from django.conf import settings
from django.core.cache import cache


cache_hit_var: ContextVar[bool] = ContextVar("store_cache_hit", default=False)
logger = logging.getLogger("wasla.performance")


def _default_ttl() -> int:
    return int(getattr(settings, "CACHE_TTL_DEFAULT", 300) or 300)


def make_cache_key(*, key: str, store_id: int) -> str:
    normalized_key = str(key or "").strip(" :")
    return f"store:{int(store_id)}:{normalized_key}"


def cache_get(key: str, store_id: int):
    cache_key = make_cache_key(key=key, store_id=store_id)
    value = cache.get(cache_key)
    if value is None:
        logger.info(
            "cache_miss",
            extra={
                "store_id": int(store_id),
                "cache_status": "MISS",
                "query_count": 0,
                "duration_ms": 0,
                "path": None,
            },
        )
        return None

    cache_hit_var.set(True)
    logger.info(
        "cache_hit",
        extra={
            "store_id": int(store_id),
            "cache_status": "HIT",
            "query_count": 0,
            "duration_ms": 0,
            "path": None,
        },
    )
    return value


def cache_set(key: str, value: Any, store_id: int, ttl: int | None = None):
    cache_key = make_cache_key(key=key, store_id=store_id)
    cache.set(cache_key, value, timeout=int(ttl or _default_ttl()))
    logger.info(
        "cache_set",
        extra={
            "store_id": int(store_id),
            "cache_status": "SET",
            "query_count": 0,
            "duration_ms": 0,
            "path": None,
        },
    )


def cache_delete(key: str, store_id: int):
    cache_key = make_cache_key(key=key, store_id=store_id)
    cache.delete(cache_key)
    logger.info(
        "cache_invalidation",
        extra={
            "store_id": int(store_id),
            "cache_status": "DELETE",
            "query_count": 0,
            "duration_ms": 0,
            "path": None,
        },
    )


def consume_cache_hit() -> bool:
    hit = bool(cache_hit_var.get())
    cache_hit_var.set(False)
    return hit

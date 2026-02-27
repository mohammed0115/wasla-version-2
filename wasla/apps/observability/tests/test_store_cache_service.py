from __future__ import annotations

from apps.core.cache import cache_delete, cache_get, cache_set
from core.infrastructure.store_cache import StoreCacheService


def test_build_key_contains_store_id_and_version(db):
    key = StoreCacheService.build_key(store_id=42, namespace="product_detail", key_parts=[101])
    assert key.startswith("store:42:product_detail:v")
    assert key.endswith(":101")


def test_get_or_set_miss_then_hit(db):
    payload = {"value": 123}

    value, hit = StoreCacheService.get_or_set(
        store_id=7,
        namespace="variant_price",
        key_parts=["p1", "v2"],
        producer=lambda: payload,
        timeout=60,
    )
    assert hit is False
    assert value == payload

    value2, hit2 = StoreCacheService.get_or_set(
        store_id=7,
        namespace="variant_price",
        key_parts=["p1", "v2"],
        producer=lambda: {"value": 999},
        timeout=60,
    )
    assert hit2 is True
    assert value2 == payload


def test_cache_set_get_delete_store_isolation(db):
    key = "permissions:dashboard:1"
    cache_set(key=key, value={"allowed": True}, store_id=1, ttl=60)
    cache_set(key=key, value={"allowed": False}, store_id=2, ttl=60)

    assert cache_get(key=key, store_id=1) == {"allowed": True}
    assert cache_get(key=key, store_id=2) == {"allowed": False}

    cache_delete(key=key, store_id=1)
    assert cache_get(key=key, store_id=1) is None
    assert cache_get(key=key, store_id=2) == {"allowed": False}

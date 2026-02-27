from __future__ import annotations

from typing import Any, Callable

from django.core.cache import cache

from apps.core.cache import cache_get, cache_set, consume_cache_hit, cache_hit_var


DEFAULT_CACHE_TIMEOUT = 300


class StoreCacheService:
    @staticmethod
    def set_cache_hit(value: bool):
        cache_hit_var.set(bool(value))

    @staticmethod
    def consume_cache_hit() -> bool:
        return consume_cache_hit()

    @staticmethod
    def _version_key(*, store_id: int, namespace: str) -> str:
        return f"store:{int(store_id)}:cache_version:{namespace}"

    @staticmethod
    def get_namespace_version(*, store_id: int, namespace: str) -> int:
        key = StoreCacheService._version_key(store_id=int(store_id), namespace=namespace)
        value = cache.get(key)
        if isinstance(value, int) and value > 0:
            return value
        cache.set(key, 1, timeout=None)
        return 1

    @staticmethod
    def bump_namespace_version(*, store_id: int, namespace: str) -> int:
        key = StoreCacheService._version_key(store_id=int(store_id), namespace=namespace)
        try:
            return int(cache.incr(key, 1))
        except Exception:
            current = cache.get(key)
            if not isinstance(current, int) or current < 1:
                current = 1
            current += 1
            cache.set(key, current, timeout=None)
            return int(current)

    @staticmethod
    def build_key(*, store_id: int, namespace: str, key_parts: list[str | int] | tuple[str | int, ...]) -> str:
        safe_parts = [str(part).strip().replace(" ", "_") for part in key_parts if str(part).strip()]
        version = StoreCacheService.get_namespace_version(store_id=int(store_id), namespace=namespace)
        suffix = ":".join(safe_parts)
        return f"store:{int(store_id)}:{namespace}:v{version}:{suffix}" if suffix else f"store:{int(store_id)}:{namespace}:v{version}"

    @staticmethod
    def get_or_set(
        *,
        store_id: int,
        namespace: str,
        key_parts: list[str | int] | tuple[str | int, ...],
        producer: Callable[[], Any],
        timeout: int = DEFAULT_CACHE_TIMEOUT,
    ) -> tuple[Any, bool]:
        key = StoreCacheService.build_key(store_id=int(store_id), namespace=namespace, key_parts=key_parts)
        value = cache_get(key=key.replace(f"store:{int(store_id)}:", "", 1), store_id=int(store_id))
        if value is not None:
            return value, True
        value = producer()
        cache_set(key=key.replace(f"store:{int(store_id)}:", "", 1), value=value, store_id=int(store_id), ttl=timeout)
        return value, False

from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Check Redis cache backend connectivity and basic read/write behavior."

    def handle(self, *args, **options):
        using_redis = str(settings.CACHES.get("default", {}).get("BACKEND", "")).endswith("RedisCache")
        key = "health:cache:redis"

        try:
            cache.set(key, "ok", timeout=10)
            value = cache.get(key)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Cache health check failed: {exc}"))
            return

        if value != "ok":
            self.stderr.write(self.style.ERROR("Cache health check failed: unexpected read value."))
            return

        backend = settings.CACHES.get("default", {}).get("BACKEND", "")
        location = settings.CACHES.get("default", {}).get("LOCATION", "")
        mode = "redis" if using_redis else "non-redis"
        self.stdout.write(
            self.style.SUCCESS(
                f"Cache health check passed ({mode}). backend={backend} location={location}"
            )
        )

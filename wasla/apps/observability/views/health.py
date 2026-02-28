from __future__ import annotations

import os

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from config.celery import app as celery_app


@require_GET
def healthz(request):
    return JsonResponse({"status": "ok"})


@require_GET
def readyz(request):
    db_ok = True
    cache_ok = True
    redis_ok = True
    celery_ok = True

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        db_ok = False

    try:
        cache.set("readyz:ping", "ok", timeout=5)
        cache_ok = cache.get("readyz:ping") == "ok"
    except Exception:
        cache_ok = False

    redis_url = (os.getenv("CACHE_REDIS_URL") or os.getenv("REDIS_URL") or "").strip()
    if redis_url:
        try:
            import redis

            client = redis.from_url(redis_url)
            redis_ok = bool(client.ping())
        except Exception:
            redis_ok = False

    try:
        inspector = celery_app.control.inspect(timeout=1.0)
        ping = inspector.ping() if inspector else None
        celery_ok = bool(ping)
    except Exception:
        celery_ok = False

    status = "ok" if db_ok and cache_ok and redis_ok and celery_ok else "degraded"
    return JsonResponse(
        {
            "status": status,
            "db": db_ok,
            "cache": cache_ok,
            "redis": redis_ok,
            "celery": celery_ok,
        },
        status=200 if status == "ok" else 503,
    )

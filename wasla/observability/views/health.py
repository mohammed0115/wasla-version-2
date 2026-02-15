from __future__ import annotations

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def healthz(request):
    return JsonResponse({"status": "ok"})


@require_GET
def readyz(request):
    db_ok = True
    cache_ok = True

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

    status = "ok" if db_ok and cache_ok else "degraded"
    return JsonResponse(
        {"status": status, "db": db_ok, "cache": cache_ok},
        status=200 if status == "ok" else 503,
    )

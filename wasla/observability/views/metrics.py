from __future__ import annotations

from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def metrics(request):
    total = cache.get("metrics:requests:total") or 0
    statuses = {}
    for code in (200, 201, 204, 400, 401, 403, 404, 409, 429, 500):
        statuses[str(code)] = cache.get(f"metrics:requests:status:{code}") or 0
    return JsonResponse({"requests_total": total, "requests_by_status": statuses})

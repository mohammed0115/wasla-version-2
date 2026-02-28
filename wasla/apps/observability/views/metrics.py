from __future__ import annotations

from django.http import HttpResponse
from django.views.decorators.http import require_GET

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


@require_GET
def metrics(request):
    payload = generate_latest()
    return HttpResponse(payload, content_type=CONTENT_TYPE_LATEST)

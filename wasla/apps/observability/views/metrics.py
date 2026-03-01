from __future__ import annotations

import logging
from django.http import HttpResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

try:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning(
        "prometheus_client not installed. Metrics endpoint will return 503. "
        "Install with: pip install prometheus-client"
    )


@require_GET
def metrics(request):
    """Prometheus metrics endpoint with graceful degradation."""
    if not PROMETHEUS_AVAILABLE:
        return HttpResponse(
            '{"error": "Prometheus client not installed. Run: pip install prometheus-client"}',
            status=503,
            content_type="application/json"
        )
    
    try:
        payload = generate_latest()
        return HttpResponse(payload, content_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Error generating metrics: {e}", exc_info=True)
        return HttpResponse(
            '{"error": "Failed to generate metrics"}',
            status=500,
            content_type="application/json"
        )

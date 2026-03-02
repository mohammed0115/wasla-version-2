from __future__ import annotations

from rest_framework import status
from rest_framework.views import APIView

from apps.cart.interfaces.api.responses import api_response
from apps.webhooks.tasks import enqueue_webhook_event


class WebhookReceiverAPI(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, provider_code: str):
        raw_body = ""
        if hasattr(request, "body") and request.body:
            raw_body = request.body.decode("utf-8", errors="replace")
        payload = request.data if isinstance(request.data, dict) else {}
        headers = {k: v for k, v in request.headers.items()}
        try:
            result = enqueue_webhook_event(
                provider_code=provider_code,
                headers=headers,
                payload=payload,
                raw_body=raw_body,
            )
        except ValueError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_400_BAD_REQUEST)

        status_code = status.HTTP_202_ACCEPTED if result.queued else status.HTTP_200_OK
        return api_response(
            success=True,
            data={
                "event_id": result.event_id,
                "status": result.status,
                "queued": result.queued,
            },
            status_code=status_code,
        )

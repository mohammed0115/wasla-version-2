from __future__ import annotations

import os
from dataclasses import dataclass

from django.conf import settings

from apps.payments.application.use_cases.handle_webhook_event import (
    HandleWebhookEventCommand,
    HandleWebhookEventUseCase,
)


@dataclass(frozen=True)
class WebhookQueueResult:
    event_id: str | None
    status: str | None
    queued: bool


def _process_webhook_now(*, provider_code: str, headers: dict, payload: dict, raw_body: str) -> WebhookQueueResult:
    event = HandleWebhookEventUseCase.execute(
        HandleWebhookEventCommand(
            provider_code=provider_code,
            headers=headers,
            payload=payload,
            raw_body=raw_body,
        )
    )
    return WebhookQueueResult(event_id=event.event_id, status=event.processing_status, queued=False)


def enqueue_webhook_event(*, provider_code: str, headers: dict, payload: dict, raw_body: str) -> WebhookQueueResult:
    if not getattr(settings, "WEBHOOK_ASYNC_ENABLED", False):
        return _process_webhook_now(
            provider_code=provider_code,
            headers=headers,
            payload=payload,
            raw_body=raw_body,
        )

    eager = (
        getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)
        or os.getenv("CELERY_TASK_ALWAYS_EAGER", "").strip().lower() in ("1", "true", "yes")
    )
    broker_url = (getattr(settings, "CELERY_BROKER_URL", "") or os.getenv("CELERY_BROKER_URL", "")).strip()
    try:
        from celery import shared_task  # noqa: F401
    except Exception:
        return _process_webhook_now(
            provider_code=provider_code,
            headers=headers,
            payload=payload,
            raw_body=raw_body,
        )

    if eager or not broker_url:
        return _process_webhook_now(
            provider_code=provider_code,
            headers=headers,
            payload=payload,
            raw_body=raw_body,
        )

    try:
        process_webhook_event.delay(
            provider_code=provider_code,
            headers=headers,
            payload=payload,
            raw_body=raw_body,
        )
    except Exception:
        return _process_webhook_now(
            provider_code=provider_code,
            headers=headers,
            payload=payload,
            raw_body=raw_body,
        )

    return WebhookQueueResult(event_id=None, status="queued", queued=True)


try:
    from celery import shared_task
except Exception:  # pragma: no cover
    shared_task = None


if shared_task:

    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_backoff=True,
        retry_backoff_max=300,
        retry_jitter=True,
        retry_kwargs={"max_retries": 5},
    )
    def process_webhook_event(self, *, provider_code: str, headers: dict, payload: dict, raw_body: str) -> str:
        result = _process_webhook_now(
            provider_code=provider_code,
            headers=headers,
            payload=payload,
            raw_body=raw_body,
        )
        return result.event_id or ""

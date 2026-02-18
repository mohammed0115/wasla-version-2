from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any

from django.conf import settings
from django.db import transaction

from apps.emails.application.services.provider_resolver import TenantEmailProviderResolver
from apps.emails.application.use_cases.send_email import SendEmailUseCase
from apps.emails.domain.types import EmailMessage
from apps.emails.models import EmailLog


def _send_email_now(*, email_log_id: int, tenant_id: int, provider: str, message: EmailMessage) -> None:
    log = EmailLog.objects.filter(id=email_log_id, tenant_id=tenant_id).first()
    if not log:
        return
    if log.status in (EmailLog.STATUS_SENT, EmailLog.STATUS_DELIVERED):
        return

    SendEmailUseCase.mark_sending(email_log_id=email_log_id)

    resolved = TenantEmailProviderResolver.resolve(tenant_id=tenant_id)
    result = resolved.gateway.send(message=message)
    SendEmailUseCase.mark_sent(email_log_id=email_log_id, provider_message_id=result.provider_message_id)


def enqueue_send_email(*, email_log_id: int, tenant_id: int, provider: str, message: EmailMessage) -> None:
    """
    Enqueue if Celery is installed; otherwise send synchronously.
    """
    eager = (
        getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)
        or os.getenv("CELERY_TASK_ALWAYS_EAGER", "").strip().lower() in ("1", "true", "yes")
    )
    broker_url = (getattr(settings, "CELERY_BROKER_URL", "") or os.getenv("CELERY_BROKER_URL", "")).strip()
    try:
        from celery import shared_task  # noqa: F401
    except Exception:
        try:
            _send_email_now(email_log_id=email_log_id, tenant_id=tenant_id, provider=provider, message=message)
        except Exception as exc:
            SendEmailUseCase.mark_failed(email_log_id=email_log_id, error=str(exc))
        return

    if eager or not broker_url:
        try:
            _send_email_now(email_log_id=email_log_id, tenant_id=tenant_id, provider=provider, message=message)
        except Exception as exc:
            SendEmailUseCase.mark_failed(email_log_id=email_log_id, error=str(exc))
        return

    try:
        send_email_task.delay(
            email_log_id=email_log_id,
            tenant_id=tenant_id,
            provider=provider,
            message_dict=asdict(message),
        )
    except Exception:
        # Broker misconfigured/unavailable; fallback to synchronous send.
        try:
            _send_email_now(email_log_id=email_log_id, tenant_id=tenant_id, provider=provider, message=message)
        except Exception as exc:
            SendEmailUseCase.mark_failed(email_log_id=email_log_id, error=str(exc))


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
    def send_email_task(self, *, email_log_id: int, tenant_id: int, provider: str, message_dict: dict[str, Any]):
        message = EmailMessage(
            to_email=message_dict.get("to_email", ""),
            subject=message_dict.get("subject", ""),
            html=message_dict.get("html", ""),
            text=message_dict.get("text", ""),
            headers=message_dict.get("headers") or {},
            metadata=message_dict.get("metadata") or {},
        )
        try:
            _send_email_now(email_log_id=email_log_id, tenant_id=tenant_id, provider=provider, message=message)
        except Exception as exc:
            SendEmailUseCase.mark_failed(email_log_id=email_log_id, error=str(exc))
            raise

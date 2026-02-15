from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from django.db import transaction
from django.utils import timezone

from emails.application.services.provider_resolver import TenantEmailProviderResolver
from emails.application.services.provider_resolver import EmailProviderNotConfigured
from emails.domain.policies import normalize_subject, normalize_template_key, validate_recipient_email
from emails.domain.types import EmailMessage
from emails.models import EmailLog


@dataclass(frozen=True)
class SendEmailCommand:
    tenant_id: int
    to_email: str
    template_key: str
    context: Mapping[str, object]
    idempotency_key: str | None = None
    metadata: Mapping[str, Any] | None = None


class SendEmailUseCase:
    @staticmethod
    def _compute_idempotency_key(*, tenant_id: int, to_email: str, template_key: str, context: Mapping[str, object]) -> str:
        payload = {
            "tenant_id": tenant_id,
            "to_email": to_email,
            "template_key": template_key,
            "context": context,
        }
        raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:64]

    @staticmethod
    def execute(cmd: SendEmailCommand) -> EmailLog:
        to_email = validate_recipient_email(cmd.to_email)
        template_key = normalize_template_key(cmd.template_key)

        idempotency_key = (cmd.idempotency_key or "").strip() or SendEmailUseCase._compute_idempotency_key(
            tenant_id=cmd.tenant_id,
            to_email=to_email,
            template_key=template_key,
            context=cmd.context,
        )

        try:
            resolved = TenantEmailProviderResolver.resolve(tenant_id=cmd.tenant_id)
        except EmailProviderNotConfigured as exc:
            with transaction.atomic():
                existing = (
                    EmailLog.objects.select_for_update()
                    .filter(tenant_id=cmd.tenant_id, idempotency_key=idempotency_key)
                    .first()
                )
                if existing:
                    return existing

                return EmailLog.objects.create(
                    tenant_id=cmd.tenant_id,
                    to_email=to_email,
                    template_key=template_key,
                    subject=template_key,
                    status=EmailLog.STATUS_FAILED,
                    provider="",
                    idempotency_key=idempotency_key,
                    last_error=str(exc),
                    metadata=dict(cmd.metadata or {}),
                )

        rendered = resolved.renderer.render(template_key=template_key, context=dict(cmd.context))
        subject = normalize_subject(rendered.subject)

        with transaction.atomic():
            existing = (
                EmailLog.objects.select_for_update()
                .filter(tenant_id=cmd.tenant_id, idempotency_key=idempotency_key)
                .first()
            )
            if existing:
                return existing

            log = EmailLog.objects.create(
                tenant_id=cmd.tenant_id,
                to_email=to_email,
                template_key=template_key,
                subject=subject,
                status=EmailLog.STATUS_QUEUED,
                provider=resolved.provider,
                idempotency_key=idempotency_key,
                metadata=dict(cmd.metadata or {}),
            )

            message = EmailMessage(
                to_email=to_email,
                subject=subject,
                html=rendered.html,
                text=rendered.text,
                headers=rendered.headers or {},
                metadata={"template_key": template_key, **{k: str(v) for k, v in (cmd.metadata or {}).items()}},
            )

            def _enqueue():
                from emails.tasks import enqueue_send_email  # local import to avoid celery hard dependency

                enqueue_send_email(
                    email_log_id=log.id,
                    tenant_id=cmd.tenant_id,
                    provider=resolved.provider,
                    message=message,
                )

            transaction.on_commit(_enqueue)

            return log

    @staticmethod
    @transaction.atomic
    def mark_sending(*, email_log_id: int) -> None:
        EmailLog.objects.filter(id=email_log_id, status=EmailLog.STATUS_QUEUED).update(status=EmailLog.STATUS_SENDING)

    @staticmethod
    @transaction.atomic
    def mark_sent(*, email_log_id: int, provider_message_id: str = "") -> None:
        EmailLog.objects.filter(id=email_log_id).update(
            status=EmailLog.STATUS_SENT,
            provider_message_id=provider_message_id or "",
            sent_at=timezone.now(),
            last_error="",
        )

    @staticmethod
    @transaction.atomic
    def mark_failed(*, email_log_id: int, error: str) -> None:
        EmailLog.objects.filter(id=email_log_id).update(
            status=EmailLog.STATUS_FAILED,
            last_error=(error or "")[:4000],
        )

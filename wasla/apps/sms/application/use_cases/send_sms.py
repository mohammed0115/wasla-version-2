from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from apps.sms.domain.entities import SmsMessage
from apps.sms.domain.errors import SmsGatewayError, SmsValidationError
from apps.sms.domain.policies import (
    normalize_recipient_list,
    validate_sms_body,
    validate_sms_sender,
)
from apps.sms.infrastructure.router import SmsGatewayRouter
from apps.sms.models import SmsMessageLog


@dataclass(frozen=True)
class SendSmsCommand:
    body: str
    recipients: list[str]
    sender: str | None = None
    scheduled_at: datetime | None = None
    tenant: object | None = None
    user: object | None = None
    metadata: dict[str, Any] | None = None
    default_country_code: str | None = None


@dataclass(frozen=True)
class SendSmsResult:
    log_id: int
    provider: str
    status: str
    provider_message_id: str | None


class SendSmsUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: SendSmsCommand) -> SendSmsResult:
        default_country_code = (cmd.default_country_code or getattr(settings, "SMS_DEFAULT_COUNTRY_CODE", "")).strip() or None

        body = validate_sms_body(cmd.body)
        recipients = normalize_recipient_list(cmd.recipients, default_country_code=default_country_code)

        resolved = SmsGatewayRouter.resolve(tenant=cmd.tenant)
        sender = validate_sms_sender(cmd.sender or resolved.default_sender)

        scheduled_at = SendSmsUseCase._normalize_scheduled_at(cmd.scheduled_at)

        tenant_id = getattr(cmd.tenant, "id", None) if cmd.tenant is not None else None
        user_id = getattr(cmd.user, "id", None) if cmd.user is not None else None

        log = SmsMessageLog.objects.create(
            tenant_id=tenant_id,
            user_id=user_id,
            provider=resolved.provider_name,
            sender=sender,
            body=body,
            recipients=list(recipients),
            scheduled_at=scheduled_at,
            status=SmsMessageLog.STATUS_QUEUED if scheduled_at is None else SmsMessageLog.STATUS_QUEUED,
            provider_response=SendSmsUseCase._json_safe({"metadata": cmd.metadata or {}}),
        )

        message = SmsMessage(
            body=body,
            recipients=recipients,
            sender=sender,
            scheduled_at=scheduled_at,
            tenant_id=tenant_id,
            metadata=cmd.metadata or {},
        )

        try:
            result = resolved.gateway.send(message)
        except SmsGatewayError as exc:
            log.status = SmsMessageLog.STATUS_FAILED
            log.error_message = str(exc)
            log.provider_response = SendSmsUseCase._json_safe({
                "provider": getattr(exc, "provider", None),
                "status_code": getattr(exc, "status_code", None),
                "error": str(exc),
            })
            log.save(update_fields=["status", "error_message", "provider_response", "updated_at"])
            raise

        log.status = SendSmsUseCase._map_status(result.status)
        log.provider_message_id = result.provider_message_id or ""
        log.provider_response = SendSmsUseCase._json_safe(result.raw or {})
        log.save(update_fields=["status", "provider_message_id", "provider_response", "updated_at"])

        return SendSmsResult(
            log_id=log.id,
            provider=result.provider,
            status=result.status,
            provider_message_id=result.provider_message_id,
        )

    @staticmethod
    def _normalize_scheduled_at(value: datetime | None) -> datetime | None:
        if value is None:
            return None

        scheduled_at = value
        if timezone.is_naive(scheduled_at):
            scheduled_at = timezone.make_aware(scheduled_at, timezone.get_current_timezone())

        if scheduled_at < timezone.now():
            raise SmsValidationError("Scheduled time must be in the future.", field="scheduled_at")

        return scheduled_at

    @staticmethod
    def _map_status(status: str) -> str:
        if status == "sent":
            return SmsMessageLog.STATUS_SENT
        if status == "scheduled":
            return SmsMessageLog.STATUS_SCHEDULED
        if status == "failed":
            return SmsMessageLog.STATUS_FAILED
        return SmsMessageLog.STATUS_QUEUED

    @staticmethod
    def _json_safe(value: Any) -> Any:
        try:
            return json.loads(json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False))
        except TypeError:
            return {"text": str(value)}

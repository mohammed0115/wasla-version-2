from __future__ import annotations

from dataclasses import asdict
import uuid

from sms.domain.entities import SmsDeliveryResult, SmsMessage


class ConsoleSmsGateway:
    """
    Development gateway: does not send anything, only returns a fake message id.
    """

    name = "console"
    supports_scheduling = True

    def send(self, message: SmsMessage) -> SmsDeliveryResult:
        message_id = f"console-{uuid.uuid4()}"
        scheduled = message.scheduled_at is not None
        status = "scheduled" if scheduled else "sent"
        return SmsDeliveryResult(
            provider=self.name,
            status=status,  # type: ignore[arg-type]
            provider_message_id=message_id,
            raw={"message": asdict(message), "note": "Console gateway (no-op)"},
        )

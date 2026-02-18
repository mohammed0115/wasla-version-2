from __future__ import annotations

from typing import Protocol

from apps.sms.domain.entities import SmsDeliveryResult, SmsMessage


class SmsGateway(Protocol):
    name: str
    supports_scheduling: bool

    def send(self, message: SmsMessage) -> SmsDeliveryResult: ...


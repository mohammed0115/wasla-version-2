from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.sms.application.use_cases.send_sms import SendSmsCommand, SendSmsUseCase
from apps.sms.domain.entities import SmsMessage
from apps.sms.domain.policies import normalize_recipient_phone
from apps.sms.infrastructure.gateways.taqnyat import TaqnyatSmsGateway
from apps.sms.models import SmsMessageLog


class SmsPoliciesTests(TestCase):
    def test_normalize_recipient_phone_accepts_ksa_formats(self):
        self.assertEqual(normalize_recipient_phone("+966500000000"), "+966500000000")
        self.assertEqual(normalize_recipient_phone("966500000000"), "+966500000000")
        self.assertEqual(normalize_recipient_phone("00966500000000"), "+966500000000")
        self.assertEqual(normalize_recipient_phone("0500000000", default_country_code="966"), "+9660500000000")


class SmsUseCaseTests(TestCase):
    @override_settings(SMS_DEFAULT_PROVIDER="console", SMS_PROVIDERS={"console": {"sender_name": "Wasla"}})
    def test_send_sms_console_success(self):
        result = SendSmsUseCase.execute(
            SendSmsCommand(
                body="Hello",
                recipients=["+966500000000"],
                sender=None,
            )
        )
        log = SmsMessageLog.objects.get(id=result.log_id)
        self.assertEqual(log.status, SmsMessageLog.STATUS_SENT)
        self.assertEqual(log.provider, "console")

    @override_settings(SMS_DEFAULT_PROVIDER="console", SMS_PROVIDERS={"console": {"sender_name": "Wasla"}})
    def test_send_sms_console_scheduled(self):
        scheduled_at = timezone.now() + timedelta(minutes=10)
        result = SendSmsUseCase.execute(
            SendSmsCommand(
                body="Hello",
                recipients=["+966500000000"],
                sender=None,
                scheduled_at=scheduled_at,
            )
        )
        log = SmsMessageLog.objects.get(id=result.log_id)
        self.assertEqual(log.status, SmsMessageLog.STATUS_SCHEDULED)
        self.assertIsNotNone(log.scheduled_at)


class TaqnyatGatewayTests(TestCase):
    def test_taqnyat_gateway_posts_expected_payload(self):
        gateway = TaqnyatSmsGateway(
            bearer_token="token",
            base_url="https://api.taqnyat.sa",
            include_bearer_as_query_param=True,
        )
        scheduled_at = timezone.now() + timedelta(minutes=30)

        with mock.patch("apps.sms.infrastructure.gateways.taqnyat.requests.post") as post:
            post.return_value.status_code = 201
            post.return_value.json.return_value = {"statusCode": 201, "messageId": "abc"}

            result = gateway.send(
                SmsMessage(
                    body="Hi",
                    recipients=("+966500000000",),
                    sender="Wasla",
                    scheduled_at=scheduled_at,
                ),
            )

            self.assertEqual(result.provider, "taqnyat")
            self.assertEqual(result.provider_message_id, "abc")

            args, kwargs = post.call_args
            self.assertEqual(args[0], "https://api.taqnyat.sa/v1/messages")
            self.assertEqual(kwargs["headers"]["Authorization"], "Bearer token")
            self.assertEqual(kwargs["params"]["bearerTokens"], "token")
            self.assertEqual(kwargs["json"]["recipients"], ["966500000000"])
            self.assertEqual(kwargs["json"]["scheduledDatetime"], scheduled_at.strftime("%Y-%m-%dT%H:%M"))

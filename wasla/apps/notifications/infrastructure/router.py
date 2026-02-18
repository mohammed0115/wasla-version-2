from __future__ import annotations

"""
Email gateway router for notifications module.

AR:
- يقرأ إعدادات البريد (global) عبر EmailConfigService (من موديول `apps/emails`).
- يجهز gateway مناسب للإرسال (SMTP فقط في هذا الموديول حالياً).

EN:
- Loads global email config via EmailConfigService (from `apps/emails`).
- Builds the appropriate gateway for sending (SMTP only for now).
"""

from dataclasses import dataclass

from apps.notifications.domain.errors import EmailGatewayError
from apps.notifications.domain.ports import EmailGateway
from apps.notifications.infrastructure.gateways.smtp import SmtpEmailGateway
from apps.emails.application.services.email_config_service import (
    EmailConfigDisabled,
    EmailConfigInvalid,
    EmailConfigMissing,
    EmailConfigService,
)


@dataclass(frozen=True)
class ResolvedEmailProvider:
    gateway: EmailGateway
    provider_name: str
    default_from_email: str


class EmailGatewayRouter:
    """Resolve an EmailGateway based on current email configuration."""

    @staticmethod
    def resolve() -> ResolvedEmailProvider:
        try:
            config = EmailConfigService.get_active_config()
        except (EmailConfigMissing, EmailConfigDisabled, EmailConfigInvalid) as exc:
            raise EmailGatewayError(str(exc)) from exc

        provider_name = config.provider
        default_from = config.from_email

        if provider_name == "smtp":
            use_ssl = (not config.use_tls) and int(config.port or 0) == 465
            return ResolvedEmailProvider(
                gateway=SmtpEmailGateway(
                    host=config.host,
                    port=config.port,
                    username=config.username,
                    password=config.password,
                    use_tls=config.use_tls,
                    use_ssl=use_ssl,
                ),
                provider_name="smtp",
                default_from_email=default_from,
            )

        if provider_name in ("sendgrid", "mailgun", "ses"):
            raise EmailGatewayError(f"Provider '{provider_name}' is not supported by notifications module.")

        raise EmailGatewayError(f"Unknown email provider: {provider_name}")

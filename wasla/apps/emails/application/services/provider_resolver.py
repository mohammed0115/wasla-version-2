from __future__ import annotations

"""
Email provider resolution.

AR:
- يحدد مزود البريد الفعّال (SMTP/SendGrid/Mailgun) بناءً على الإعدادات الحالية.
- يبني Gateway Adapter مناسب ويُرجعه لباقي الـ use cases.

EN:
- Resolves the active email provider (SMTP/SendGrid/Mailgun) from configuration.
- Builds the correct gateway adapter for use cases.
"""

from dataclasses import dataclass

from apps.emails.application.services.email_config_service import (
    EmailConfigDisabled,
    EmailConfigInvalid,
    EmailConfigMissing,
    EmailConfigService,
)
from apps.emails.domain.ports import EmailGatewayPort, TemplateRendererPort
from apps.emails.infrastructure.providers.mailgun_gateway import MailgunEmailGateway
from apps.emails.infrastructure.providers.sendgrid_gateway import SendGridEmailGateway
from apps.emails.infrastructure.providers.smtp_gateway import SmtpEmailGateway
from apps.emails.infrastructure.renderers.django_renderer import DjangoTemplateRendererAdapter


class EmailProviderNotConfigured(Exception):
    """Raised when no valid email provider configuration exists."""

    pass


@dataclass(frozen=True)
class ResolvedEmailBackend:
    """Resolved backend used by the application layer to send emails."""

    provider: str
    from_email: str
    from_name: str
    gateway: EmailGatewayPort
    renderer: TemplateRendererPort


class TenantEmailProviderResolver:
    """Resolves and builds the active email backend for a tenant."""

    @staticmethod
    def resolve(*, tenant_id: int) -> ResolvedEmailBackend:
        try:
            config = EmailConfigService.get_active_config()
        except (EmailConfigMissing, EmailConfigDisabled, EmailConfigInvalid) as exc:
            raise EmailProviderNotConfigured(str(exc)) from exc

        provider = config.provider
        from_email = config.from_email
        from_name = ""

        renderer: TemplateRendererPort = DjangoTemplateRendererAdapter()

        if provider == "smtp":
            use_ssl = (not config.use_tls) and int(config.port or 0) == 465
            gateway = SmtpEmailGateway(
                from_email=from_email,
                from_name=from_name,
                host=config.host or None,
                port=config.port or None,
                username=config.username or None,
                password=config.password or None,
                use_tls=bool(config.use_tls),
                use_ssl=use_ssl,
                timeout=None,
            )
        elif provider == "sendgrid":
            gateway = SendGridEmailGateway(api_key=config.password, from_email=from_email, from_name=from_name)
        elif provider == "mailgun":
            gateway = MailgunEmailGateway(
                api_key=config.password,
                domain=config.username,
                base_url=config.host or "https://api.mailgun.net",
                from_email=from_email,
                from_name=from_name,
            )
        elif provider == "ses":
            raise EmailProviderNotConfigured("SES provider is optional and not enabled in phase 1.")
        else:
            raise EmailProviderNotConfigured(f"Unknown email provider: {provider!r}")

        return ResolvedEmailBackend(
            provider=provider,
            from_email=from_email,
            from_name=from_name,
            gateway=gateway,
            renderer=renderer,
        )

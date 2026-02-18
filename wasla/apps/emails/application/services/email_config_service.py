from __future__ import annotations

from dataclasses import dataclass

from apps.emails.application.services.crypto import CredentialCrypto
from apps.emails.models import GlobalEmailSettings


class EmailConfigMissing(Exception):
    pass


class EmailConfigDisabled(Exception):
    pass


class EmailConfigInvalid(Exception):
    pass


@dataclass(frozen=True)
class EmailConfig:
    provider: str
    host: str
    port: int
    username: str
    password: str
    from_email: str
    use_tls: bool
    enabled: bool


class EmailConfigService:
    @staticmethod
    def get_active_config() -> EmailConfig:
        qs = GlobalEmailSettings.objects.all().order_by("id")
        count = qs.count()
        if count == 0:
            raise EmailConfigMissing("GlobalEmailSettings is missing.")
        if count > 1:
            raise EmailConfigInvalid("Multiple GlobalEmailSettings rows found.")

        row = qs.first()
        if not row or not row.enabled:
            raise EmailConfigDisabled("Email sending is disabled.")

        password = ""
        if row.password_encrypted:
            try:
                password = CredentialCrypto.decrypt_text(row.password_encrypted)
            except Exception as exc:
                raise EmailConfigInvalid("Unable to decrypt email credentials.") from exc

        config = EmailConfig(
            provider=row.provider,
            host=row.host or "",
            port=int(row.port or 0),
            username=row.username or "",
            password=password,
            from_email=row.from_email or "",
            use_tls=bool(row.use_tls),
            enabled=bool(row.enabled),
        )
        EmailConfigService.validate_config(config)
        return config

    @staticmethod
    def validate_config(config: EmailConfig) -> None:
        if not config.from_email:
            raise EmailConfigInvalid("from_email is required.")

        provider = config.provider
        if provider == GlobalEmailSettings.PROVIDER_SMTP:
            if not config.host:
                raise EmailConfigInvalid("SMTP host is required.")
            if not config.port:
                raise EmailConfigInvalid("SMTP port is required.")
            if not config.username:
                raise EmailConfigInvalid("SMTP username is required.")
            if not config.password:
                raise EmailConfigInvalid("SMTP password is required.")
        elif provider == GlobalEmailSettings.PROVIDER_SENDGRID:
            if not config.password:
                raise EmailConfigInvalid("SendGrid API key is required.")
        elif provider == GlobalEmailSettings.PROVIDER_MAILGUN:
            if not config.username:
                raise EmailConfigInvalid("Mailgun domain is required.")
            if not config.password:
                raise EmailConfigInvalid("Mailgun API key is required.")
        elif provider == GlobalEmailSettings.PROVIDER_SES:
            raise EmailConfigInvalid("SES provider is optional and not enabled in phase 1.")
        else:
            raise EmailConfigInvalid(f"Unknown email provider: {provider!r}")

        return

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings

from apps.sms.domain.errors import SmsConfigurationError
from apps.sms.domain.ports import SmsGateway
from apps.sms.infrastructure.gateways.console import ConsoleSmsGateway
from apps.sms.infrastructure.gateways.taqnyat import TaqnyatSmsGateway
from apps.sms.models import TenantSmsSettings


@dataclass(frozen=True)
class ResolvedSmsProvider:
    gateway: SmsGateway
    default_sender: str
    provider_name: str
    provider_config: dict[str, Any]


class SmsGatewayRouter:
    @staticmethod
    def resolve(*, tenant: object | None = None) -> ResolvedSmsProvider:
        provider_name, provider_config, sender = SmsGatewayRouter._resolve_provider_config(tenant=tenant)
        gateway = SmsGatewayRouter._build_gateway(provider_name, provider_config)
        return ResolvedSmsProvider(
            gateway=gateway,
            default_sender=sender,
            provider_name=provider_name,
            provider_config=provider_config,
        )

    @staticmethod
    def _resolve_provider_config(*, tenant: object | None) -> tuple[str, dict[str, Any], str]:
        default_provider = getattr(settings, "SMS_DEFAULT_PROVIDER", "console")
        providers: dict[str, dict[str, Any]] = getattr(settings, "SMS_PROVIDERS", {}) or {}

        provider_name = default_provider
        provider_config: dict[str, Any] = dict(providers.get(provider_name, {}) or {})
        sender = str(provider_config.get("sender_name") or getattr(settings, "SMS_DEFAULT_SENDER_NAME", "Wasla"))

        tenant_settings = SmsGatewayRouter._get_tenant_settings(tenant)
        if tenant_settings and tenant_settings.is_enabled:
            provider_name = tenant_settings.provider or provider_name
            provider_config = dict(providers.get(provider_name, {}) or {})
            provider_config.update(tenant_settings.config or {})
            if tenant_settings.sender_name:
                sender = tenant_settings.sender_name

        return provider_name, provider_config, sender

    @staticmethod
    def _get_tenant_settings(tenant: object | None) -> TenantSmsSettings | None:
        if tenant is None:
            return None
        tenant_id = getattr(tenant, "id", None)
        if not tenant_id:
            return None
        return TenantSmsSettings.objects.filter(tenant_id=tenant_id).first()

    @staticmethod
    def _build_gateway(provider_name: str, provider_config: dict[str, Any]) -> SmsGateway:
        if provider_name == TenantSmsSettings.PROVIDER_CONSOLE:
            return ConsoleSmsGateway()

        if provider_name == TenantSmsSettings.PROVIDER_TAQNYAT:
            return TaqnyatSmsGateway(
                bearer_token=str(provider_config.get("bearer_token") or ""),
                base_url=str(provider_config.get("base_url") or "https://api.taqnyat.sa"),
                timeout_seconds=int(provider_config.get("timeout_seconds") or 10),
                include_bearer_as_query_param=bool(provider_config.get("include_bearer_as_query_param") or False),
            )

        raise SmsConfigurationError(f"Unknown SMS provider: {provider_name!r}")


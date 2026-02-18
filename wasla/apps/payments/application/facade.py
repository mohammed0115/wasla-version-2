from __future__ import annotations

from apps.payments.domain.ports import PaymentGatewayPort, VerifiedEvent
from apps.payments.infrastructure.adapters import (
    ApplePayGatewayAdapter,
    MadaGatewayAdapter,
    MastercardGatewayAdapter,
    TabbyGatewayAdapter,
    TamaraGatewayAdapter,
    VisaGatewayAdapter,
)
from apps.payments.infrastructure.gateways.dummy_gateway import DummyGateway
from apps.payments.infrastructure.gateways.sandbox_stub import SandboxStubGateway
from apps.payments.models import PaymentProviderSettings
from apps.tenants.models import StorePaymentSettings


class PaymentGatewayFacade:
    _registry: dict[str, type[PaymentGatewayPort]] = {
        DummyGateway.code: DummyGateway,
        SandboxStubGateway.code: SandboxStubGateway,
        MadaGatewayAdapter.code: MadaGatewayAdapter,
        VisaGatewayAdapter.code: VisaGatewayAdapter,
        MastercardGatewayAdapter.code: MastercardGatewayAdapter,
        ApplePayGatewayAdapter.code: ApplePayGatewayAdapter,
        TabbyGatewayAdapter.code: TabbyGatewayAdapter,
        TamaraGatewayAdapter.code: TamaraGatewayAdapter,
    }

    @classmethod
    def get(cls, provider_code: str, *, tenant_id: int | None = None) -> PaymentGatewayPort:
        key = (provider_code or "").strip().lower()
        adapter_cls = cls._registry.get(key)
        if not adapter_cls:
            raise ValueError(f"Unknown payment provider: {provider_code}")
        if tenant_id is None:
            raise ValueError("Tenant context is required for payment providers.")
        if not cls._store_allows_provider(tenant_id=tenant_id, provider_code=key):
            raise ValueError("Payment provider is not enabled for this store.")

        settings = PaymentProviderSettings.objects.filter(
            tenant_id=tenant_id,
            provider_code=key,
            is_enabled=True,
        ).first()
        if not settings:
            raise ValueError("Payment provider is not configured or disabled.")
        return adapter_cls(settings=settings)

    @classmethod
    def available_providers(cls, tenant_id: int | None = None) -> list[dict]:
        if tenant_id is None:
            return [
                {"code": code, "name": adapter.name}
                for code, adapter in cls._registry.items()
            ]

        store_settings = StorePaymentSettings.objects.filter(tenant_id=tenant_id).first()
        if not store_settings or not store_settings.is_enabled:
            return []

        allowed_codes = set(cls._registry.keys())
        if store_settings.mode == StorePaymentSettings.MODE_DUMMY:
            allowed_codes = {"dummy", "sandbox"}
        elif store_settings.mode != StorePaymentSettings.MODE_GATEWAY:
            return []

        settings_qs = PaymentProviderSettings.objects.filter(
            tenant_id=tenant_id,
            is_enabled=True,
            provider_code__in=list(allowed_codes),
        ).order_by("id")

        providers: list[dict] = []
        for settings in settings_qs:
            adapter_cls = cls._registry.get(settings.provider_code)
            if not adapter_cls:
                continue
            display_name = settings.display_name or adapter_cls.name
            providers.append({"code": settings.provider_code, "name": display_name})
        return providers

    @classmethod
    def resolve_for_webhook(
        cls,
        provider_code: str,
        *,
        headers: dict,
        payload: dict,
        raw_body: str = "",
    ) -> tuple[PaymentGatewayPort, VerifiedEvent, int | None]:
        key = (provider_code or "").strip().lower()
        adapter_cls = cls._registry.get(key)
        if not adapter_cls:
            raise ValueError(f"Unknown payment provider: {provider_code}")

        settings_list = list(
            PaymentProviderSettings.objects.filter(
                provider_code=key,
                is_enabled=True,
            )
        )
        if not settings_list:
            raise ValueError("No enabled payment provider configuration found.")

        last_error: Exception | None = None
        for settings in settings_list:
            adapter = adapter_cls(settings=settings)
            try:
                verified = adapter.verify_callback(
                    payload=payload,
                    headers=headers,
                    raw_body=raw_body,
                )
                return adapter, verified, settings.tenant_id
            except ValueError as exc:
                last_error = exc
                continue

        raise ValueError(str(last_error or "Invalid signature."))

    @classmethod
    def _store_allows_provider(cls, *, tenant_id: int, provider_code: str) -> bool:
        settings = StorePaymentSettings.objects.filter(tenant_id=tenant_id).first()
        if not settings or not settings.is_enabled:
            return False
        if settings.mode == StorePaymentSettings.MODE_GATEWAY:
            return True
        if settings.mode == StorePaymentSettings.MODE_DUMMY:
            return provider_code in {"dummy", "sandbox"}
        return False
